# How BioManager 1.0 was tested

Before 1.0.0, BioManager was put through a stress test on top of its own
test suite. Six testers each took one area and used the app like a lab would,
and like an attacker or a failing machine would. Every test was written down
with what it did, what should happen and what did happen. The problems they
found were fixed, and the fixes were tested again the same way.

The testers were AI agents (Claude Code), each working on its own copy of the
lab with its own server, database and browser, and the rules in the brief
below. All names in the reports are the demo lab's fictional people. The full
reports are in [docs/testing/](testing/).

| Area | What it covered | Report |
| --- | --- | --- |
| **Security** | every route signed out and as each role, notebook and personal-database privacy, cross-site requests in a real browser, stored script injection on 27 pages, uploads, sessions and cookies, sign-in throttling, open redirects, the setup code, lab copies, guest passes, SQL injection on 52 parameters, error pages, headers, API tokens | [security.md](testing/security.md) |
| **Pilot: a mouse lab** | [PILOT.md](PILOT.md)'s eight weeks for an eight-person lab on a lab server: setup, sign-ups and roles, importing a 352-mouse messy colony sheet (every mouse checked against the sheet), cage cards and labels, breeding, weaning, experiments, the notebook, several people working at once | [pilot-mouse.md](testing/pilot-mouse.md) |
| **Pilot: fish, flies, worms and inventory** | a zebrafish / Drosophila / C. elegans lab with a custom Xenopus database and six inventories, on SQLite and then PostgreSQL: racks and tanks, flips by temperature, crosses and collections, orders to stock, imports of messy sheets, labels, search, offline use, a lab copy restored to PostgreSQL | [pilot-other.md](testing/pilot-other.md) |
| **Data integrity** | whether a fact reads the same everywhere it appears (a mouse in 9 places, before and after changes in 5), exports and imports back, SQLite → PostgreSQL, lab copies (every value compared), undo and redo of every batch type, awkward text, dates and time zones, SQLite vs PostgreSQL parity | [integrity.md](testing/integrity.md) |
| **Robustness** | 100,000 mice, many people saving the same thing at once, killing the server mid-import and mid-upgrade, PostgreSQL stopping, a full disk, a locked or damaged database file, every release's database upgraded, 12-minute soaks on both databases | [robustness.md](testing/robustness.md) |
| **Running a lab server** | the published release files and the docs only: install, moving a lab in, updating and rolling back, backups, restores, off-site copies, "the server is lost", people joining and leaving, guests, rotating secrets, the watchdog, the desktop app's update check | [deploy.md](testing/deploy.md) |

## What they found

405 tests: **263 passed, 92 warnings, 50 failures.** No test found a way in
for someone signed out, and 1,625 SQL injection attempts and 108 pages of
planted script ran nothing. What they did find:

| Area | Tests | Pass | Warn | Fail |
| --- | ---: | ---: | ---: | ---: |
| Security | 54 | 37 | 15 | 2 |
| Pilot: mouse lab | 110 | 84 | 13 | 13 |
| Pilot: fish, flies, worms, inventory | 85 | 56 | 28 | 1 |
| Data integrity | 55 | 24 | 15 | 16 |
| Robustness | 44 | 22 | 15 | 7 |
| Running a lab server | 57 | 40 | 6 | 11 |
| **All** | **405** | **263** | **92** | **50** |

The serious ones, all fixed for 1.0:

| Severity | Finding | Fixed |
| --- | --- | --- |
| Critical | With members allowed to keep lab copies, a **guest pass could download the whole database**, and a member's copy held everyone's password hashes and private notebook pages | Guests can't keep copies. A member's copy holds what they can see in the app; an admin's is the whole lab. A test fails if a new table isn't classified |
| Critical | **Merged Cage # cells** in an imported sheet put 51 of 352 mice in no cage or the wrong one | Merged cells count for each row; a new cage for a rack place never takes a number the sheet uses |
| Critical | **Undo → redo → Undo** left the mice with no cage, while the Audit log said they were back | Records a batch created are undone last |
| Critical | A mouse sheet row open since before a colleague's change **silently undid it** when any cell was saved (a sac'd mouse came back alive) | A row sends what each cell showed; unchanged cells are left as the database has them |
| Critical | "The server is lost → from off-site", followed word for word, **restored an empty lab** | A server with no accounts sends nothing off-site; the runbook picks the copy by its time |
| High | People saving at the same moment lost mice (8 of 28 simultaneous **New mouse** saved) with a false "ID already used" | Saves that take the next number retry with a fresh one |
| High | **New mouse refused** on every press after an old, lower-numbered mouse was re-imported | Numbers are handed out above the highest ever given |
| High | Two cages dropped on one rack place at once both answered "ok": **up to six cages in one place** | One cage per place is a database rule (revision 0006) |
| High | A **lab copy taken while people work** had mice pointing at cages it didn't hold | The copy is read in one transaction |
| High | Editing any cell **removed line breaks** from a mouse's note and transgenes | A one-line cell's copy of a multi-line value counts as unchanged |
| High | **Sac** on mice already dead overwrote their date of death | Kept |
| High | Import read `15-03-26` as 2015-03-26 and a day-first lab's `03/04/2026` as 4 March, left `12-May-26` blank, and **accepted birth dates in the future** | Two-digit groups are day or month first; Lab setup's date style decides; text months are read; a future birth date is left blank and kept in the notes |
| High | Imported cages all belonged to whoever ran the import, so members couldn't wean or breed their own | They belong to their mice's owner |
| High | A mistyped files path in a **restore emptied the data folder**, signing key included | Both backups are checked before anything changes |
| High | After an update the newest backup was of the **already-updated** database, which "Updating went wrong" said to restore | No start-up backup while one from the last 12 hours exists |

Every other finding is listed in its report. Most of the medium ones are
fixed too: weaning is undoable, the Excel export is a real workbook the
importer reads back, no export cell runs as a formula, Sign out ends a
session for good and re-enabling an account doesn't revive old ones,
search is case-blind in every script and takes `%` literally, a database
that doesn't answer gets a page saying so instead of a bare error, the app
won't start on an emptied database file or one a newer version made,
off-site copies are pruned, and the watchdog no longer raises false alarms.

### Known and not fixed in 1.0

Left as they are, each with a reason; they are in the reports too.

- **Speed at 100,000 mice.** The cages sheet takes about 5 s and litters
  about 7 s at that size (mice about 3 s), and four people opening big
  sheets at once slows Home to 4–9 s. A lab that size is far beyond the
  pilots; paging the big sheets is the planned fix.
- **Anyone can pause sign-in for a username** with ten wrong passwords (15
  minutes). That is the price of throttling guesses per name; the lab's
  own admin can still reset the password.
- **Uploaded files open for any signed-in member who has the link.** Their
  names are random 64-bit tokens, and the link is only on the record.
- **An admin's lab copy holds everything**, private notebook pages and
  password hashes included, because it is the restore point for the whole
  lab. The guide says to treat that computer like the server.
- **Smaller things**: the browser's CSV export writes "–" for empty cells; a
  calendar event across midnight shows on its first day only; the calendar's
  "today" follows the browser, not the lab's time zone; water readings
  outside a system's targets aren't flagged; a label printer's own font has
  no CJK or emoji; the backup image needs Debian's package mirrors to build.

## Tested again after the fixes

A seventh tester re-ran the original reproductions (the same scripts, the
same sheets) against the fixed code, on SQLite and, where the original ran
there, PostgreSQL: [retest.md](testing/retest.md).

**64 findings re-run: 57 fixed, 5 partly, 2 still failing.** Across every
server log of the re-test there was one HTTP 500, during a deliberate
PostgreSQL outage. What it found was then fixed as follows:

| Re-test result | Now |
| --- | --- |
| A title line of 3 of 5 cells was still taken as the header | Fixed, with a test |
| Concurrent CSV imports: the ones that lost the race answered "empty CSV" | Fixed: a retried save reads the uploaded file again |
| On PostgreSQL an Undo could still overwrite an edit saved while it ran (1–2 in 4 runs) | Undo now locks what it changes and checks again; covered by the suite, not yet re-run under load |
| While PostgreSQL was down, 1 of 431 replies was a bare 500 (the error page read the database) | The error pages now render without it; not yet re-run under an outage |
| **New in the fixes:** the CSV export's formula guard turned `+/+` into `'+/+` on the way back in | Fixed: the importer takes the guard off again, with a test |
| `load-image.sh` still said `up -d` without `--build`; a disabled member's lab-copy key worked again on re-enabling | Fixed |
| Two identical New mouse posts at the same instant make two mice (before, the second was refused only by the ID clash) | Left: a real double-click in the browser sends one request (ROB-19 passed) |
| An import into a lab that doesn't use `breeding` maps it to `breeder` | Left: that is the lab's built-in name for it |
| Redoing an import gives a re-made cage back to the importer; 3 of about 339 New mouse saves on SQLite, while lab copies were being taken, were still refused; the sign-up limit counts per worker; `aIex` (capital I) is accepted beside `alex` | Left, low; listed for after 1.0 |
| The server stopped answering for about 3 minutes once during a flood of CSP reports | Not reproduced in three more runs; to watch |

## The test suite and the upgrade check

Besides the stress test, every change runs the project's own tests
(`scripts/test.sh`, [DEVELOPMENT.md](DEVELOPMENT.md#running-the-tests)) on
both databases, and the upgrade check: a demo lab made by **every release
since 0.2.0** is opened by this version and must upgrade with nothing lost.
For 1.0:

| Check | SQLite | PostgreSQL 16 |
| --- | --- | --- |
| Test suite (`scripts/test.sh`) | 1,369 tests pass (5 skipped) | 1,365 tests pass (19 skipped) |
| Upgrade check, every release 0.2.0 → 0.10.2 | 14 of 14: upgraded, nothing lost, pages open | 14 of 14 |

The one new database change for 1.0, one cage per rack place (revision
0006), was also run on a database that already had three cages in one
place: the oldest kept it, the other two were taken off the rack with a
line in their notes, and the rule was in place afterwards.

## Function test: a wet lab's everyday work

After the stress test, a second test asked a different question: can a
wet-lab-heavy lab plan and record its everyday experiments in BioManager,
and what is tedious? Five testers played a lab manager and four researchers
(cloning, cell culture and CRISPR, protein purification, RNA and Westerns)
in one lab for two simulated weeks. The findings, the chores that repeat
and the functions they suggest are in [testing/wet-lab.md](testing/wet-lab.md).

## How it was done

Each tester got the same brief: use only your own server, port, database
and folder; never change the code under test; don't contact anything
outside the machine; record what you actually ran and saw ("not tested" is
fine, a guessed pass is not); and give each finding its steps, what
happened, what should have, the evidence and a suspected cause. Evidence
(scripts, logs, screenshots, the generated sheets and databases) was kept
per area; the scripts can be run again against a newer version.

- **Servers**: gunicorn with the repository's `gunicorn.conf.py`, as on a lab
  server (1 worker with 4 threads on SQLite, 3 on PostgreSQL), and the dev
  server for the desktop app's case. The server test used the published
  0.10.1 and 0.10.2 release files and Docker Compose.
- **Databases**: SQLite and PostgreSQL 16.
- **Browsers**: headless Chromium, desktop and 390 px phone sizes, light
  and dark.
- **Data**: the demo lab (`scripts/demo-data.py`), the 100,000-mouse lab
  (`scripts/load-test.py`), fresh labs set up through the app, and messy
  sheets built to include merged cells, mixed date styles, duplicate IDs,
  total lines, unknown people and odd values.
- **Not covered**: printing on real label printers, phone cameras scanning
  real labels, real Tailscale and Let's Encrypt, a Mac or Windows desktop
  window, and weeks of calendar time (the pilots' eight weeks ran in an
  afternoon, so daily reminders were not seen arriving day by day).
