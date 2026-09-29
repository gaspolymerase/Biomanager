# Pilot-mouse: eight weeks of a mouse lab, compressed

Area `pilot-mouse` of the BioManager 1.0 pre-release test. The eight weeks of
`docs/PILOT.md` played out for an 8-person mouse lab on a lab-server-like
setup, as several people, mostly through the real UI in Chromium.

## 1. Scope and environment

- **Code**: `the repository` at `76371cf` (`git describe`: v0.10.1-5-g76371cf; the app reports `0.10.1+dev`). Read only; nothing was edited.
- **Server**: gunicorn with the repo's `gunicorn.conf.py` (`wsgi:app`, production mode, 3 workers x 4 threads, `preload_app`), `BIOMANAGER_HTTPS=0`, `BIOMANAGER_TELEMETRY=0`, bound to 127.0.0.1:5101. Script: `evidence/start-server.sh`, log: `evidence/server.log`.
- **Database**: PostgreSQL 16 in Docker (`pg-pilotmouse`, host port 55501), fresh and empty at the start. The checks read it directly with psycopg (read-only queries).
- **Browser**: Playwright Chromium 1194, headless. Desktop 1400-1500 x 900-1000. Phone 390 x 844, mobile + touch.
- **People** (all fictional): `riley` (first admin, lab manager), members `dana`, `eli`, `fern`, `gus`, `hana`, `casey` (Animal care), `fiona` (Facility manager).
- **Data**: a messy colony workbook I generated (`evidence/files/colony-messy.xlsx`, 352 mice in 110+ cages, script `evidence/scripts/make_sheets.py`). The truth for each row is in `colony-truth.json`, so every imported mouse could be checked, not only a sample. The lab ended with about 390 mice, 117 cages, 105 litters, 1 experiment with 40 body weights and 10 recorded injection days, and 1 signed, witnessed and amended notebook page.
- **How**: the UI (Playwright) wherever a person would work: sign-up, setup questions, approvals, Import from Excel, cage cards, the phone views, Add many, Batches, the cage breeding and weaning dialogs, inline sheet edits, the rack grid (drag on desktop, Move on a phone), Ctrl+K, the experiment page, bench mode, the notebook editor, Feedback, the Usage report, exports. **HTTP** (the same POSTs the page makes, with the user's session) where that was faster, or to check that the server refuses what the UI hides: permissions, bulk selection-bar actions, experiment steps and records, signatures, sharing, comments, and the concurrency runs.
- **Time**: the "eight weeks" took one real afternoon (2026-09-29). Anything that depends on the calendar was not tested for real: overdue reminders, daily notifications, the weekly progression in the Usage report (every change falls in one week), nightly backups. Backups, restore tests and upgrades belong to other areas.
- **Re-running**: `evidence/scripts/p0_register.py` ... `p11b_batch_race.py`, in order, against a fresh server. Results go to `evidence/results.jsonl`, one row per test; a later row with the same ID replaces the earlier one.
- **Error pages**: the whole run produced **no HTTP 500** (`grep '" 50[0-9] ' server.log` is empty) and no JavaScript page errors on the pages watched.

## 2. Test log

110 tests: **84 PASS, 13 WARN, 13 FAIL**.

| ID | What | How (steps, users, data) | Expected | Result | Evidence |
| --- | --- | --- | --- | --- | --- |
| PM-01 | Wrong setup code refused | register first account with 0000-0000-0000 | refused with message | **PASS** | shots/p0-badcode.png |
| PM-02 | First admin with setup code | register riley with printed setup code | admin created, redirect to sign in | **PASS** | shots/p0-created.png |
| PM-03 | Setup questions | riley answers survey: lab name, TZ America/New_York, Mouse colony+Samples+Reagents+Orders, 3 racks 6x8 A1 naming, calendar+notebook | lab set up, lands on Home with Getting started | **PASS** | shots/p1-after-setup.png url=http://127.0.0.1:5101/home |
| PM-04 | Sign-up waits for approval | dana registers at /register then tries to sign in | told to wait for an admin; not signed in | **PASS** | shots/p2-pending-signin.png msg: BioManager Your account is waiting for a lab admin to approve it. Sign in  Use your shared lab account to work on the central BioManager database.  Username Password Sign in  Need an account? Create o |
| PM-05 | Approve members and set roles | riley: Settings > Manage users: Approve x7 (confirm dialog), set casey=Animal care, fiona=Facility manager | 7 active accounts with the right roles | **PASS** | shots/p2-users-approved.png |
| PM-06 | Approved members can sign in | each of 7 approved users signs in | reaches Home/setup | **PASS** |  |
| PM-07 | Manage users page readable | riley opens Settings > Manage users at 1400x900 | role picker readable | **WARN** | shots/p2-users-approved.png: the Role <select> is squashed to ~15 px; the current role shows only in the badge |
| PM-08 | Import: title line with two cells above the header | colony-titled.xlsx: row1 'Colony list' + 'Updated:' '09/03/2026', header on row 2 | row 2 recognised as the header (ID, Sex, DOB, Cage, Owner) | **FAIL** | shots/p3-titled-match.png headers seen: Colony list, Column 2, Column 3, Updated:, 09/03/2026 |
| PM-09 | Import messy colony sheet: column matching | riley: Mice > Import from Excel > colony-messy.xlsx (352 mice, merged title row, header row 3, 14 columns) | every column matched sensibly | **PASS** | import-mapping.txt, shots/p3-messy-match.png |
| PM-10 | Import: preview lists every skipped/changed row | Preview the import | all warnings visible | **WARN** | import-preview.txt: 5 date notes max per column, then 'and 138 more' with no way to see them |
| PM-11 | Import: 352 mice created, one batch | Import 353 mice (4.7 s on Postgres) | 352 mice | **WARN** | import-verify.txt: 353 created - the extra is the mid-sheet 'Total rack 1-2 so far:' line (#1) |
| PM-12 | Import: TOTAL line at the bottom left out | last row TOTAL | not imported | **PASS** | preview: 'Row 359 looks like the sheet's total' |
| PM-13 | Import: mid-sheet subtotal line | row 'Total rack 1-2 so far: … 187 mice' | left out like TOTAL | **FAIL** | became mouse #1 with note 'ID in the spreadsheet: Total rack 1-2 so far:' |
| PM-14 | Import: vertically merged Cage # cells | 23 cages whose Cage # cell is merged over their 2-5 mice | every mouse in its cage | **FAIL** | import-verify.txt 'cage wrong: 51': mice lose their cage, or are put in a NEW cage whose number is the next sheet cage (cage 106 holds #1018 from sheet cage 105 + cage 106's own mice) |
| PM-15 | Import: DOB day-first text (25/03/2026) + Excel dates | DOB column with >12 day values | read day first | **PASS** | no wrong DOBs among d/m/Y and real dates |
| PM-16 | Import: DOB written as 12-May-26 text | 19 rows with d-Mon-yy text | read, or kept in notes | **FAIL** | 19 DOBs blank, text not kept anywhere; preview names 5 of them |
| PM-17 | Import: Sac date column, all values ambiguous (01/09/2026 day-first) | 16 sacked mice | right dates, or a way to say day-first | **FAIL** | 16 dates of death wrong (2026-09-01 -> 2026-01-09, one now in the future 2026-12-09); only a one-line note; no day/month switch |
| PM-18 | Import: duplicate mouse IDs | IDs 1005, 1010, 1100 appear twice | second gets next free ID, sheet ID in notes | **PASS** | got #2, #3, #4 with 'ID in the spreadsheet: 1005' (fills low gap, not after 2004) |
| PM-19 | Import: unknown owners | 'Jo', 'Dr. Visitor' | importer's, name in notes, warned | **PASS** | 77 mice riley's with 'Owner in the spreadsheet: Jo' |
| PM-20 | Import: owner name variants | dana / Dana Member / Eli / FERN / Hana | matched to accounts | **PASS** | 0 owner mismatches |
| PM-21 | Import: odd sexes | Male/female/m/f/♂/♀/M?/unk | tidied, odd ones kept as typed | **WARN** | all tidied; 'M?' silently becomes M (the doubt is lost); 'unk' kept |
| PM-22 | Import: odd statuses | Breeding/exp/Stock/to genotype/holding/retired breeder/pending | mapped or kept with a warning | **PASS** | 0 mismatches; unknowns warned |
| PM-23 | Import: rack + position | Rack 1 / rack 2 / R3(no such rack) / positions a1, 'C 4', 'D-5' | placed; unknown rack warned | **PASS** | positions parsed; 'There is no rack called R3' warned |
| PM-24 | Import: cage owner | cages made by the import | cage belongs to its mice's owner | **FAIL** | all 115 cages owned by riley (the importer); members' mice sit in the admin's cages (253 mice) |
| PM-25 | Import: litter with two different DOBs in the sheet | L-9000: #2002 02/05/2026, #2003 09/05/2026 | a warning | **FAIL** | #2002's DOB silently becomes 2026-05-09; no warning |
| PM-26 | Import: future DOB typo | #2004 DOB 12/03/2062 | refused as Add many / litters do | **FAIL** | imported with DOB 2062-03-12 (litter L-9001) |
| PM-27 | Import: extra columns into notes | Ear punch, Comments | kept in notes | **PASS** | 0 lost |
| PM-28 | Cage cards on a sheet | riley: Cages > Cage cards (sheet of cards, any printer) | one card per cage with QR | **PASS** | shots/p5-cards-sheet.png url=http://127.0.0.1:5101/labels/cards/cages?scope=mine |
| PM-29 | Cage cards on a Brother QL 62x29 roll | Print on: Brother QL 62 x 29 > Show | one label a page, typed to fit | **PASS** | shots/p5-cards-62x29.png |
| PM-30 | Download for Zebra (.zpl) | Zebra 4x2.5in cage card > Download for Zebra | valid ZPL, one label per cage, QR | **PASS** | files/cages-labels.zpl: 115 labels, 59744 bytes |
| PM-31 | Decode a printed card's QR | screenshot the first card's QR, decode with OpenCV | a URL to that cage on this server | **PASS** | shots/p5-qr.png -> http://127.0.0.1:5101/colony?view=cages&scope=all&card=1#cage-116 |
| PM-32a | Scanned card opens on a phone (dana) | dana signed in, 390x844 phone viewport, open decoded URL | that cage opens, readable, no sideways scroll | **PASS** | shots/p5-phone-dana.png horizontal overflow=0px errors=[] |
| PM-32b | Scanned card opens on a phone (casey) | casey signed in, 390x844 phone viewport, open decoded URL | that cage opens, readable, no sideways scroll | **PASS** | shots/p5-phone-casey.png horizontal overflow=0px errors=[] |
| PM-33a | Admin hands imported cages to dana | riley: Cages, tick 18 cages holding only dana's mice, set owner = dana (POST /colony/cages/bulk) | 18 cages now dana's | **PASS** | status 200, 18 cages owned by dana |
| PM-33b | Admin hands imported cages to eli | riley: Cages, tick 22 cages holding only eli's mice, set owner = eli (POST /colony/cages/bulk) | 22 cages now eli's | **PASS** | status 200, 22 cages owned by eli |
| PM-34 | Member sets their cage's purpose inline | dana: Cages sheet, cage 131 Purpose -> Breeding (autosave) | saved | **PASS** | db purpose=('Breeding', False) |
| PM-35 | Litter born today | dana: expand cage 131 > Litter born today > OK | litter date today; weaning due in 21 days | **PASS** | Recorded a litter born today in cage 131: weaning is due Oct 20. |
| PM-36 | Genotyping: create the litter's pups | dana: cage 131 > Genotyping > Pups 7 > Create litter | 7 pups with status geno, owner dana | **PASS** | Created litter L-9002 with 7 pups in cage 131. pups=[2005, 2006, 2007, 2008, 2009, 2010, 2011] |
| PM-37 | Home shows the genotyping queue | dana opens Home after the litter | cage 131's pups in the genotyping queue | **PASS** | shots/p6-home-dana.png |
| PM-38 | Wean early pups and move them | dana: cage 131 > Wean (P0: asks 'These pups are young' > Wean early) > rows F: 4 pups card W-F1, M: 3 pups card W-M1 > Wean and move | asked first; two new cages owned by dana, sexes set, litter weaned | **PASS** | dialog: 'These pups are young\n\nThe pups in cage 131 are 0 days old. Weaning is due at P21.\n\nWean them early anyway?\n\nCancel\nWean '; prefilled rows=3 ['', '', '2005, 2006, 2007, 2008, 2009, 2010, 2011']; flash: Distributed 7 mice and weaned cage 131.; moved=[(2005, 'F', '216', 'W-F1', 'dana'), (2006, 'F', '216', 'W-F1', 'dana'), (2007, 'F', '216', 'W-F1', 'dana'), (2008, 'F', '216', 'W-F1', 'dana'), (2009, 'M', '217', 'W-M1', 'dana'), (2010, 'M', '217', 'W-M1', 'dana'), (2011, 'M', '217', 'W-M1', 'dana')] |
| PM-39 | Add many: 4 females, 2 males | eli: Mice > Add many, DBH-Cre, cage 'new', DOB 2026-09-01, 4 F + 2 M > preview > Create | 6 mice, one new cage per sex, owned by eli | **PASS** | 6 new; [(2017, 'M', '219', 'eli', datetime.date(2026, 9, 1)), (2016, 'M', '219', 'eli', datetime.date(2026, 9, 1)), (2015, 'F', '218', 'eli', datetime.date(2026, 9, 1)), (2014, 'F', '218', 'eli', datetime.date(2026, 9, 1)), (2013, 'F', '218', 'eli', datetime.date(2026, 9, 1)), (2012, 'F', '218', 'eli', datetime.date(2026, 9, 1))]; flash: Created 6 mice — #2012 to #2017. Undo |
| PM-40 | Add many refuses a future DOB | eli: Add many with DOB 2027-01-05 | refused | **PASS** | shots/p7-addmany-future.png Rows 1, 2: the date of birth is in the future. Correct it before creating. |
| PM-41 | Undo an Add many from Batch history | eli: Batches > Undo on the Add many batch | the 6 mice removed | **PASS** | 366->360; Undid 9 change(s). |
| PM-42 | Undo flagged after someone else edited | eli: Add many 3; casey edits one's note; eli: Batches | batch flagged, plain Undo not offered | **PASS** | Batches shows '1 record(s) changed after this batch' and only a red 'Undo anyway'; its confirm text ('Undo …? This reverses 3 record(s).') doesn't say casey's edit will be thrown away; the script clicked it and the edited mouse was deleted (audit 1516/1517) |
| PM-43 | Member sees another member's mouse read-only | dana: Mice (Everyone), eli's mouse #1001 | cells disabled | **PASS** | disabled flags={True} |
| PM-44 | Member can't change another's mouse by a direct POST | dana POSTs /colony/mice/354/update (status sac, owner dana) | refused, unchanged | **PASS** | HTTP 409; before=('eli', 'breeder', 'fighting, separate\nEar punch: LL') after=('eli', 'breeder', 'fighting, separate\nEar punch: LL') |
| PM-45 | Member can't move another's cage | dana POSTs /colony/cages/116/place | 403 | **PASS** | HTTP 403 {"error":"That record belongs to eli. Ask them, or an admin, to make the change.","ok":false}  |
| PM-46 | Member can't sac another's mouse in a batch | dana POSTs bulk-sac with eli's mouse | skipped | **PASS** | HTTP 200, dod=None |
| PM-47 | Member can't make herself admin | dana POSTs /admin/users/2/role role=admin | refused | **PASS** | HTTP 200, role=[('member',)] |
| PM-48 | Animal care records a weight on a member's mouse | casey POSTs weight 23.4 g for dana's #1028 | saved | **PASS** | HTTP 200 [(23.4, datetime.date(2026, 9, 29))] |
| PM-49 | Animal care moves a member's cage | casey places dana's cage (of #1028) on Rack 3 | moved | **PASS** | HTTP 200 (3, 6, 7) |
| PM-50 | Owner told when care moves their cage | dana's notifications after casey's move | a notification (README: 'when someone moves … animals') | **WARN** | ['riley gave you 18 cages: cage 108, cage 196, cage 172, cage 198, cage 204 and 13 more', 'Waiting for genotyping: 6 mice'] |
| PM-51 | Animal care creating an experiment | casey POSTs /colony/experiments/create | README: care 'not experiments' | **WARN** | HTTP 200, made=1 |
| PM-52 | Animal care can't open /setup | casey opens /setup | refused | **PASS** | HTTP 200 landed http://127.0.0.1:5101/home |
| PM-53 | Animal care can't open /admin/users | casey opens /admin/users | refused | **PASS** | HTTP 200 landed http://127.0.0.1:5101/colony |
| PM-54 | Animal care and the notebook | casey POSTs /notebook/pages/create-quick | README: care 'not … notebooks' | **WARN** | HTTP 200, pages 0->1 |
| PM-55 | Facility manager adds a rack | fiona: POST /colony/racks/save Rack 4 6x8 | created | **PASS** | HTTP 200 |
| PM-56 | Facility manager can't manage accounts | fiona opens /admin/users | refused | **PASS** | HTTP 200 http://127.0.0.1:5101/colony |
| PM-57 | Facility manager can't create an experiment | fiona POSTs experiments/create | refused | **FAIL** | HTTP 200 made=1 |
| PM-58 | Facility manager renames a survey-made rack | fiona: rack dialog, Rack 1 -> 'A-Left' (a name that another rack already has) | renamed, or a clear refusal | **PASS** | HTTP 200; racks=[(1, 'Rack 1'), (2, 'Rack 2'), (3, 'Rack 3'), (4, 'Rack 4'), (5, 'A-Left')] |
| PM-58b | Facility manager renames Rack 1 | fiona: Rack 1 -> 'Left rack' | renamed | **PASS** | [(1, 'Left rack'), (2, 'Rack 2'), (3, 'Rack 3'), (4, 'Rack 4'), (5, 'A-Left')] |
| PM-59 | Two people edit the same mouse at once | casey sets #1028 status = breeder; dana, whose sheet was open before, then types a note in the same row | both changes kept (or dana warned) | **FAIL** | after casey: status='breeder'; after dana: status='' note='tail mark renewed'; dana saw: '' |
| PM-60 | Drag a cage on the rack grid | riley: Cages > Rack grid > Rack 2, drag cage (id 169) to empty cell r1 c3 | moved and saved | **PASS** | shots/p7-rack-grid.png (2, 1, 1)->(2, 1, 3) |
| PM-61 | Move a cage on a phone (Move button) | dana on 390px phone: Rack grid > Rack 2 > Move > tap their cage > tap empty cell | moved | **PASS** | shots/p7-phone-rack.png -> (1, 1), sideways overflow 0px |
| PM-62 | Sac two of your own mice | dana ticks 2 mice > Sac (POST bulk-sac) | date of death today, status sac | **PASS** | HTTP 200 [(datetime.date(2026, 9, 29), 'sac'), (datetime.date(2026, 9, 29), 'sac')] |
| PM-63 | Ctrl+K search finds a mouse by ID | dana: Ctrl+K, type 1001 | the mouse is listed | **PASS** | shots/p7-search.png |
| PM-64 | Search page | dana /search?q=Room 214 | results, no error | **PASS** | HTTP 200 |
| PM-65 | Calendar shows colony dates | dana opens Calendar | weaning/genotyping dates shown | **PASS** | shots/p7-calendar.png |
| PM-66 | Mouse IDs not reused | eli: Add many 6 (#2012-2017), Undo, Add many 3 | new IDs after 2017 (README: 'never reused') | **WARN** | the 3 new mice got #2012-#2014 again; a card or note that named #2012 now points at another mouse |
| PM-67 | Shrinking a full rack | fiona: Rack 2 (6x8, ~40 cages) resized to 2x2 | refused, or cages clearly listed as unplaced | **WARN** | rack now (2, 2); 26 cages outside the grid; flash:  |
| PM-68 | Start an experiment and add mice in two groups | dana: create 'TAM induction cohort 1' (start 2026-09-20); tick 4 mice > Add to experiment as TAM, 4 as Vehicle | 8 mice in 2 groups | **PASS** | [('TAM', 4), ('Vehicle', 4)] |
| PM-69 | Regimen: manipulations with doses per body weight | dana: Tamoxifen 75 mg/kg i.p. at 20 mg/mL days 1-5 (TAM), corn oil 3.75 mL/kg days 1-5 (Vehicle), body weight days 1,3,5,7,9 | 3 manipulations planned | **PASS** | 200/200/200 [(1, 'injection', 'Tamoxifen', '1–5', 'TAM'), (2, 'injection', 'Corn oil', '1–5', 'Vehicle'), (3, 'reading', '', '1, 3, 5, 7, 9', '')]  |
| PM-70 | Dose per body weight worked out from the latest weight | preview for TAM on day 1 | amount = weight x 75 mg/kg, volume at 20 mg/mL | **PASS** | #1028 22.5 g -> 1.69 mg / 84.4 µL (expected 1.688 mg, 84.4 uL) |
| PM-71 | Record days | dana records days 1-5 of both injections | 10 records, each mouse's amount kept | **PASS** | 10 records; day-1 TAM entry: {'subject': 'mouse:381', 'label': '#1028', 'mouse': 381, 'mouse_id': 1028, 'grams': 22.5, 'amount': '1.69 mg', 'volume': '84.4 µL'} |
| PM-72 | Recording a day in the future is refused | record body weight done_on 2026-10-30 | 400 | **PASS** | 400 {"error":"It can't be recorded as done on a day still to come.","ok":false}  |
| PM-73 | Experiment page: sheet, chart, tests by day | dana opens the experiment | sheet of mice, body-weight chart, tests table | **PASS** | shots/p8-experiment-page.png; svgs=53; errors=[] |
| PM-74 | Body weights shown as recorded | dana: experiment > Body weight tab | each recorded value in its day column | **PASS** | shots/p8-bodyweight-tab.png: all 40 values as recorded |
| PM-75 | Export to Excel | experiment Export (.xlsx), checked every sheet | Readout long (8 mice x 5 days + any other weights), wide, Manipulations with amounts, Tests by day | **PASS** | files/TAM-induction-cohort-1.xlsx: 41 readout rows = 40 recorded + casey's 23.4 g on 09-29 (day 10), amounts match (1.69 mg / 84.4 uL at 22.5 g); Welch day 9 p=0.035 * |
| PM-76 | Bench mode on a phone opens | dana, 390px phone, /experiments/<id>/bench | one animal at a time, big numbers, no sideways scroll | **PASS** | shots/p8-bench-phone.png overflow=0 inputs=0 errors=[] |
| PM-77 | Weigh a mouse in bench mode on a phone | dana, phone: bench > Weigh: Body weight > type 21.9 > Next | saved as today's weight of the first mouse | **PASS** | shots/p8-bench-weigh1.png, p8-bench-weigh2.png; db [(1028, 21.9, datetime.date(2026, 9, 29))]; errors [] |
| PM-78 | Chart when one mouse is weighed outside the plan | casey weighed #1028 on 09-29 (routine care weight); dana opens the experiment chart | the plan days, or that point marked n=1 | **WARN** | shots/p8-bodyweight-tab.png: a Day 10 column appears and the TAM line jumps to that one mouse (n=1 of 4) as if the group gained 3 g |
| PM-79 | Experiment > Add to notebook | dana: experiment page > Add to notebook | a notebook page with the live experiment block | **PASS** | shots/p9-notebook-page.png; page (2, 'TAM induction cohort 1', 'experiment'); url http://127.0.0.1:5101/notebook?page=2 |
| PM-80 | Write in the notebook page | dana types a results paragraph in the editor | saved within a few seconds | **PASS** | body has text: True |
| PM-81 | Insert a data sheet | dana: '/' then 'data sheet' Enter | a data sheet block in the page | **PASS** | shots/p9-datasheet.png; body tail: '"],["Treated",""]],"showPlot":true,"showStats":true,"chart":{"type":"bar","x":0,"y":[1],"group":-1,"error":"sem","fit":false,"logY":false},"stats":{"group":0,"value":1,"test":"auto","control":""}}\n```' |
| PM-82 | Share a page with a lab mate to edit | dana shares the page with eli (edit) | eli told, can open it | **PASS** | 200 [('Dana Member shared “TAM induction cohort 1” with you',)] |
| PM-83 | Unshared member can't read the page | gus GET /notebook/api/pages/<id> | 404/403 | **PASS** | HTTP 404 |
| PM-84 | Comment with an @mention | eli comments on the quoted passage '@dana nice…' | dana notified with a link to the comment | **PASS** | 200 [('Eli Member mentioned you on “TAM induction cohort 1”', '/notebook?page=2#comment-1')] |
| PM-85 | Sign a page | dana signs: wrong password, then hers | wrong refused; signed, fingerprinted, experiment frozen | **PASS** | 403/200 [('sign', 'dana', 'e99d9f163bbb0ca59e4c0f54dc4d6e1d43c26037864e7217296386f29c8bd450')] |
| PM-86 | A signed page is locked | eli (editor) opens the signed page and types | no change | **PASS** | contenteditable=false; shots/p9-locked-eli.png |
| PM-87 | A signed page can't be deleted | dana POSTs delete on it | refused | **PASS** | HTTP 200, still there=1 |
| PM-88 | Witness | dana witnesses own (refused); gus, not shared (refused); eli witnesses | only eli's counts | **PASS** | 409/404/200 |
| PM-89 | Amend a signed page | dana: amend with reason 'x' (refused), then a real reason; type an amendment | reason kept with signatures; page editable again | **PASS** | 400/200; history [('sign', 'dana', ''), ('witness', 'eli', ''), ('amend', 'dana', 'Adding day 11 weights as asked by eli')] |
| PM-90 | Version history | dana: page versions | a version per editing session and the signed one | **PASS** | 3 versions: [('', 'auto'), ('Signed by Dana Member', 'manual'), ('', 'auto')] |
| PM-91 | Restore a version | dana restores the 'Signed by' version | page text back to that version | **PASS** | HTTP 200 |
| PM-92 | Members send Feedback notes | dana (problem), eli (idea), gus (question): sidebar Feedback from the Cages page > Send | 3 notes, each with the page it came from | **PASS** | [('dana', 'problem', 'open', '/colony?view=cages', 'The import put all our cages under Riley', '0.10.1+dev'), ('eli', 'idea', 'open', '/colony?view=cages', 'Could the rack grid show the sex split o', '0.10.1+dev'), ('gus', 'question', 'open', '/colony?view=cages', 'How do I print cards for just Rack 2?', '0.10.1+dev')] |
| PM-93 | Admin reads Feedback and marks one done | riley: Feedback > Done on the first note | status done | **PASS** | [('open',), ('open',), ('done',)]; shots/p10-feedback-admin.png |
| PM-94 | Members see only their own notes | dana opens Feedback | not eli's or gus's | **PASS** |  |
| PM-95 | Usage report is admins only | dana GET /feedback/usage | 403 | **PASS** | HTTP 403 |
| PM-96 | Usage report text for the Monday email | riley: Feedback > Usage report > the text at the bottom | 8 weeks of counts, people this week, no names | **PASS** | usage-report.txt; names found: [] |
| PM-97 | Export every mouse to Excel and CSV | riley: Mice (Everyone) > Export > Excel, CSV | every mouse, incl. ended ones, with notes and dates of death | **PASS** | db 360; excel 360 (missing []), csv 360; notes w/ ear punch 242/242; header ('Mouse_ID', 'Active', 'Age_weeks', 'Age_days', 'Gender', 'Transgene_1', 'Transgene_2', 'Transgene_3', 'Transgene_4', 'Cage_ID', 'Rack', 'Position', 'Cage_Location', 'Owner', 'Litter_ID', 'DOB', 'Status', 'Date_of_Death', 'Note') |
| PM-97b | Mice > Export > Excel is a real workbook | riley: Mice > Export > Excel; open the file | an .xlsx Excel opens without complaint (and Import from Excel takes back) | **FAIL** | files/export-mice-mice_export.xls is tab-separated text named .xls (first bytes b'Mous'); Import from Excel refuses .xls ('old-style .xls file') |
| PM-98 | Export the cages sheet (CSV) | riley: Cages (Everyone) > Export | every cage (117 in db) | **PASS** | files/export-cages-2026-09-29.csv: 117 rows vs 117 in the database |
| PM-99 | Export the litters sheet (CSV) | riley: Litters (Everyone) > Export | every litter (105 in db) | **PASS** | files/export-litters-2026-09-29.csv: 105 rows vs 105 in the database |
| PM-100 | Export my data (a member leaving) | dana: Settings > Export my data | a zip of their records: mice, cages, experiments and weights, notebook | **WARN** | files/biomanager_dana_20260929.zip: ['mice.csv', 'plasmids.csv', 'notebook/Experiments/TAM induction cohort 1.md', 'profile.json']; mice 64/64; missing: ['cages', 'experiments', 'weights']; mice.csv columns ['mouse_id', 'gender', 'genotype', 'status', 'owner', 'cage_id', 'litter_id', 'dob', 'dod', 'note'] |
| PM-101 | A member leaves: records handed on, account disabled | riley: Overview; Cages bulk owner dana->eli; Mice bulk owner dana->eli (selection bar posts); Manage users > Disable dana; dana tries to sign in | nothing left with dana; dana can't sign in; dana's notebook page kept | **PASS** | left with dana (mice, cages)=(0, 0); eli now owns 139 mice; sign-in stays on http://127.0.0.1:5101/login; notebook page kept=1; shots/p10-overview.png |
| PM-102 | A leaving member's experiment | after the hand-over, the experiment's owner | a way to hand it on (Overview / Racks & boxes cover cages and racks) | **WARN** | experiment still owned by disabled 'dana': only an admin can edit it; no hand-over found in Overview |
| PM-103 | Seven people press New mouse at the same moment | 28 simultaneous POST /colony/mice/create from 7 accounts, nobody types an ID (p11_concurrency.py); then 2 simultaneous from hana | every mouse saved with its own ID | **FAIL** | only 8 of 28 saved; the other 20 answered 302 with the flash 'That mouse ID is already used. Choose another.' (Postgres log: 21 x duplicate key ix_mice_mouse_id). With just 2 presses at once, 1 of 2 was lost |
| PM-104 | Seven people save Add many at the same moment | 7 simultaneous Add many > Create (5 mice each, cage 'new'), 3 gunicorn workers | 35 mice with distinct IDs in 7 new cages | **FAIL** | created 10 (distinct IDs 10, cages 2); per owner [('eli', 5), ('hana', 5)]; messages {'gus': ['That cage ID is already used. Choose another.'], 'casey': ['That cage ID is already used. Choose another.'], 'riley': ['That cage ID is already used. Choose another.'], 'fiona': ['That cage ID is already used. Choose another.'], 'fern': ['That cage ID is already used. Choose another.'], 'eli': ['Created 5 mice — #2025 to #2029. '], 'hana': ['Created 5 mice — #2030 to #2034. ']} |
| PM-105 | Two page loads at once show a false error | hana's two simultaneous requests (above), the second one's redirect to Mice | no error | **WARN** | flash 'That key is already used. Choose another.': Postgres 'duplicate key app_settings_pkey Key (key)=(did:6:colony)', from the Getting started milestone app/lab.py:568 |
| PM-106 | Undo of the import after weeks of work is guarded | riley: Batches, the 'import 353 mice' row | flagged, plain Undo not offered | **PASS** | 2026-09-29 13:08	create	import 353 mice from colony-messy.xlsx mice	353	RIL	 141 record(s) changed after this batch — reverting would throw those later edits away. 	 Undo anyway |

## 3. Findings

Ranked by severity. File:line references are in `the repository` at 76371cf. Where a cause is marked *suspected*, I read the code but did not prove it with a debugger.

### F1. Critical: merged Cage cells in Excel put mice in the wrong cage, or in none (PM-14)
- **Steps**: riley: Mice > Import from Excel > `colony-messy.xlsx`. In it, 23 cages have their `Cage #` cell merged down over their 2-5 mice rows, as people often do in colony sheets.
- **What happened**: 51 mice have the wrong cage. When the rack/position cells are blank too, the extra mice have **no cage**: #1002-#1004 of sheet cage 101 are unhoused. When the row still has a rack and position, each extra mouse gets a **new cage with the next free number**. That number belongs to a cage further down the sheet, and when the import reaches that cage it adds its mice to the new one. So **cage 106 holds #1018 from sheet cage 105 as well as cage 106's own five mice**, and cages 122 and 142 are mixed the same way. The preview's only hint is buried among 180 notes ("Row 21 (#1018): Rack 2 · E3 already holds cage 105…").
- **Expected**: a merged cell's value applies to every row it covers, or the preview warns that merged cells were found.
- **Evidence**: `evidence/import-verify.txt` ("cage wrong: 51"), and `evidence/merged-cages-sql.txt` (the mice in cages 105/106/122/142).
- **Suspected cause**: `read_workbook` loads with `read_only=True, data_only=True` (app/sheet_import.py:130-139), which hands back `None` for every merged cell except the top-left one, and nothing fills them in. Then `MiceTarget.create` (app/sheet_import.py:486-491) calls `new_owned_cage` → `next_cage_id` for a rack+position with no cage number. That makes a number the sheet uses later, and `get_or_create_cage` (app/services.py:811) quietly joins the later rows to it.

### F2. High: two people editing the same mouse: the second silently undoes the first (PM-59)
- **Steps**: dana has the Mice sheet open. casey (Animal care) sets dana's #1028 Status to *breeder* from casey's own browser, and it saves. Then dana, whose page was loaded before, types a note in the same row.
- **What happened**: dana's autosave sends the whole row as dana's page shows it. Status goes back to empty, and casey's change is lost with no message to either of them. The audit log shows casey's change and then dana's revert (`evidence/lost-update-audit.txt`).
- **Expected**: only the changed field is saved, or dana is told that the row changed underneath.
- **Suspected cause**: the row form posts every cell, and `populate_mouse_from_form` sets `gender`, `status`, `note` and transgenes from the form without a check (app/app.py:1001-1006). Only date of death and cage location have a `_was` guard (`form_changed`). On a lab server, with care staff and owners working on the same animals, this will happen.

### F3. High: pressing New mouse or saving Add many at the same moment loses entries, with a misleading message (PM-103, PM-104)
- **Steps**: `evidence/scripts/p11_concurrency.py` and `p11b_batch_race.py`. 28 simultaneous **New mouse** POSTs from 7 accounts; 2 simultaneous from one person; then 7 simultaneous **Add many > Create** of 5 mice with cage `new`.
- **What happened**: only **8 of 28** new mice were saved. With just two presses at once, **1 of 2** was saved. With Add many, **2 of 7** were saved (10 of 35 mice). Every failed request answered 302 with the flash *"That mouse ID is already used. Choose another."* or *"That cage ID is already used. Choose another."*, although nobody typed an ID. Postgres logged 21 x `duplicate key … ix_mice_mouse_id`. No 500s.
- **Expected**: IDs handed out safely (retry, lock or sequence), and every mouse saved.
- **Suspected cause**: `next_mouse_id` is `max()+1` inside the request's transaction (app/services.py:693); cage IDs come from `reserve_cage_ids`/`next_cage_id` (app/services.py:755). Two workers read the same max. The IntegrityError handler (app/app.py:372-396) turns this into "choose another".

### F4. High: dates the import can't read are dropped; ambiguous ones are read wrong, with no way to say "day first" (PM-16, PM-17, PM-10)
- **DOB as `12-May-26` text** (19 rows, a common CSV/Excel text form): the date of birth is left blank, and the original text is **not kept anywhere** (not in the notes). The preview names only the first 5 of them ("isn't a date, so it's left blank").
- **Sac date, all ambiguous** (`01/09/2026`, meant day first like the lab's DOB column): all 16 were read month first. 2026-09-01 became 2026-01-09, and one became 2026-12-09, **a date of death in the future**. The only sign is one line: "Its dates were read month first". There is no control to switch it. As a result, 8 of those mice are now "ended over 90 days ago" and **hidden** from the Mice sheet behind *Show them*.
- The preview caps "Worth a look" at 40 lines, then shows "and 138 more" with no way to see them (app/templates/sheet_import.html:236). The per-column notes are cut to 5 (`notes[:5]`, app/sheet_import.py:375).
- **Expected**: `d-Mon-yy` is read. An unreadable value is kept in the notes, as unknown owners are. Each date column gets a day-first/month-first choice on the match page. Every note can be seen.
- **Cause**: `tidy_dates` (app/sheet_import.py:325-375) handles ISO, Excel serials, `parse_date` (ISO-like only, app/services.py:72-83) and `d/m/y`. Anything else becomes `""`.

### F5. High: every cage the import makes belongs to the admin who ran it (PM-24)
- **Steps**: riley imports the lab's sheet, as PILOT.md says the champion does.
- **What happened**: all 115 cages belong to riley, including those holding only dana's or eli's mice (253 mice). Members open their own cages read-only ("Read only: riley's cage", `shots/p5-phone-dana.png`), so they can't record a litter, wean, set a purpose or move their own cage on the rack grid. dana's first Feedback note in the simulation says exactly this.
- **Workaround that worked**: Cages > tick > set owner (PM-33). But the admin has to do it person by person, and it can't sensibly fix a cage that holds several owners' mice.
- **Suspected cause**: `get_or_create_cage` makes the cage with `owner=g.user` (app/services.py:818-822), and `new_owned_cage` does the same (app/app.py:2696). The import never passes the row's owner.

### F6. Medium: the import accepts a future date of birth (PM-26)
Row `#2004`, DOB `12/03/2062`, went in as 2062-03-12, with no refusal and no warning. Add many refuses the same date (PM-40, "the date of birth is in the future"). *Suspected cause*: `MiceTarget.create` calls `populate_mouse_from_form` directly; `future_birth` (app/app.py:946) is checked only in the create/update routes.

### F7. Medium: two rows of one litter with different DOBs: the earlier mouse is silently re-dated (PM-25)
L-9000: #2002 is 02/05/2026 and #2003 is 09/05/2026. Both end up 2026-05-09, with no warning. *Cause*: `get_or_create_litter` re-dates an existing litter to the newest DOB it is given (app/services.py:765-772); the import doesn't compare.

### F8. Medium: a subtotal line in the middle of the sheet becomes a mouse (PM-13, PM-11)
The row `Total rack 1-2 so far: … 187 mice` became **mouse #1** (alive, riley's, note "ID in the spreadsheet: Total rack 1-2 so far:"). It then shows on every export and census, and the preview said "Import 353 mice" for 352. The bottom `TOTAL` line was left out correctly. *Cause*: `is_total` (app/sheet_import.py:186-199) accepts only a first cell that is exactly total/subtotal/sum. A row with no sex, DOB, cage or genotype could be flagged.

### F9. Medium: a title line with two cells is taken as the header (PM-08)
In `colony-titled.xlsx`, row 1 is `Colony list … Updated: 09/03/2026` and row 2 is the real header. The match page shows columns "Colony list, Column 2, Column 3, Updated:, 09/03/2026". There is no way to choose the header row, so the only fix is editing the sheet. *Cause*: `split_header` takes the first row with ≥2 filled cells (app/sheet_import.py:166-183).

### F10. Medium: "Excel" export of Mice isn't an Excel file, and Import from Excel won't take it back (PM-97b)
Mice > Export > **Excel** downloads `mice_export.xls`, which is **tab-separated text** (first bytes `Mous`). Excel warns that the format and extension don't match. Import from Excel refuses any `.xls` ("That's an old-style .xls file…"). The *content* is complete: 360 of 360 mice, ended ones included, notes intact (PM-97). *Cause*: `export_mouse_rows` writes TSV for "excel" (app/services.py:1256-1258). The experiment export, by contrast, is a real .xlsx (PM-75).

### F11. Medium: care and facility roles can create experiments and notebook pages (PM-51, PM-54, PM-57)
The Manage users role text (app/access.py:36-39) and the README say Animal care "may change any lab's animals … but not experiments, notebooks or settings", and Facility manager is "Animal care, plus …". Yet casey and fiona could both **create an experiment** (`/colony/experiments/create`), and casey could **create a notebook page**. Settings, Lab setup and accounts were correctly refused (PM-52, 53, 56). Maybe the intent is "not other people's experiments", but then the role text says more than the code does. *Cause*: `create_experiment` has no role check (app/app.py:2204-2225).

### F12. Medium: Export my data for a leaving member leaves most of their work out (PM-100)
dana's zip holds `mice.csv` (64/64, but only `genotype`, not transgenes or cage position), `plasmids.csv`, dana's own notebook pages and `profile.json`. It leaves out dana's **cages**, the **experiment** (manipulations, doses, 40 body weights), weights generally, and inventory items. README: "downloads your own records". *Code*: app/app.py:1831-1910.

### F13. Low-medium: a leaving member's experiment can't be handed on (PM-102)
After riley moved dana's mice and cages to eli and disabled dana, the experiment "TAM induction cohort 1" still belongs to the disabled `dana`. Only an admin can change it. Overview and the bulk actions cover cages, mice and racks, but not experiments.

### F14. Low: mouse IDs are handed out again after an Undo (PM-66)
eli made #2012-#2017 with Add many, undid it, and the next Add many got #2012-#2014 again. The README says IDs "are assigned in order and never reused". Printed cards or notes naming #2012 now point at another mouse.

### F15. Low: resizing a full rack smaller gives no warning (PM-67)
fiona set Rack 2 (6 x 8, about 40 cages) to 2 x 2. It saved, and 26 cages fell outside the grid (unplaced). Their positions were kept, and resizing back restored them, so nothing was lost; but there was no confirm or count.

### F16. Low: the body-weight chart treats one extra weighing as a group day (PM-78)
casey weighed #1028 on 09-29, outside the plan. The experiment then gains a *Day 10* column, and the TAM mean line jumps to that single mouse's 23.4 g (n=1 of 4), as if the group had gained 3 g (`shots/p8-bodyweight-tab.png`). The exported tests table is fine (days 1-9).

### F17. Low: a false "That key is already used. Choose another." after two page loads at once (PM-105)
Two of hana's requests at the same moment. The redirect to Mice showed that flash, caused by a race on the Getting-started milestone setting `did:6:colony` (Postgres: duplicate `app_settings_pkey`; app/lab.py:568).

### F18. Low: smaller things
- **PM-07**: on Manage users at 1400 px wide, the Role `<select>` is squashed to about 15 px, so the current role shows only in the badge (`shots/p2-users-approved.png`).
- **PM-21**: the sex `M?` is tidied to `M`, and the doubt is lost (`unk` is kept as typed).
- **PM-50**: when Animal care moves a member's cage to another rack, the owner gets no notification (the README's bell list says "moves … animals").
- **PM-42 (passes, with a note)**: after a later edit, Batches shows the blocker and offers only a red **Undo anyway**, but its confirm text ("Undo …? This reverses 3 record(s).") doesn't say that casey's edit will be thrown away. Clicking it deleted casey's edited mouse.
- **Speed**: Cages sheet 3.5 s for 115 cages (Mice 1.0 s for 353 mice) on this machine.

## 4. Numbers

| What | Value |
| --- | --- |
| Colony sheet | 352 mice, 110 + 7 cages, 14 columns, 23 merged Cage cells, 1 title row, 1 subtotal and 1 TOTAL line |
| Import (preview + run) | 353 rows created in **4.7 s** (Postgres, 3 workers); 1 batch |
| Import accuracy vs the sheet | owner 0 wrong, sex 0 wrong, status 0 wrong, genotype 0 wrong, extra columns to notes 0 lost; **cage 51 wrong**, **DOB 19 lost**, **date of death 16 wrong**, 1 junk mouse, 1 litter re-dated, 1 future DOB |
| Page loads (riley, 1500 px) | Mice 1.0 s, Cages 3.5 s, Litters 1.0 s, Breeders 0.7 s, Experiments 0.8 s |
| Cage cards | 115 cards on a sheet; Brother 62x29 and Zebra 4x2.5 views; ZPL 115 labels, 59.7 kB; QR decoded (OpenCV) to `/colony?view=cages&scope=all&card=1#cage-116`, which opened and expanded cage 101 on a 390 px phone |
| Concurrency (lab server) | New mouse: 8/28 saved (7 users x 4 at once), 1/2 saved (2 at once); Add many: 2/7 saved |
| Experiment | 8 mice, 2 groups, 3 manipulations, 10 recorded injection days, 40 body weights; dose 75 mg/kg at 22.5 g → 1.69 mg / 84.4 µL (correct); Welch day 9 p = 0.035 |
| Exports | Mice CSV/"Excel" 360/360; Cages CSV 117/117; Litters CSV 105/105; experiment .xlsx 4 sheets, 41 readout rows |
| HTTP 5xx during the whole run | 0 |

## 5. What worked well (for balance)

The setup code, survey and approvals; column matching by meaning (all 14 messy headers matched right); owner names in any form; unknown owners kept in the notes; the TOTAL line; duplicate IDs; rack and position parsing (`b3`, `C 4`, `D-5`). Cage cards on every stock, ZPL, and a scanned QR opening the cage on a phone, read-only or editable by role. Litter born today → Genotyping → early-wean confirm → Wean and move. Add many, with its future-date refusal. Batch undo, and its guard. Every member-vs-member permission probe (UI read-only and a direct POST: 409/403/skipped). The experiment regimen's dose maths, records, chart, tests, export and bench mode on a phone. The notebook: add from experiment, editor, data sheet, share, 404 for the unshared, @mention, sign (wrong password refused), lock, no delete, witness rules, amend with reason, versions, restore. Feedback, Usage report (counts only, no names, admins only). Hand-over and disabling a leaving member. No 500s at all.

## 6. Clean-up

The gunicorn server on 5101 was stopped and the `pg-pilotmouse` container removed at the end of the run. Everything else is under `testing/pilot-mouse/`.
