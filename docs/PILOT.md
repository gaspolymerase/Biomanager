# Running a pilot

How to try BioManager with two or three labs before 1.0, and know at the
end whether it works for them. Eight weeks, one champion in each lab, and
two things built into the app: **Feedback** (in the sidebar, under Help)
and the **Usage report** (for admins, on the Feedback page).

## Choosing the labs

Pick labs that differ, so each finds different problems:

| | Why |
| --- | --- |
| A mouse lab of 6–15 people, still on Excel | the colony, cage cards, weaning and breeders every day |
| A fish, fly or worm lab | the other databases, tanks and vials, and label printers |
| A lab with animal-facility staff, or that must sign in with the institution's account | care and facility roles, institution sign-in, a lab server |

Each needs a **champion**: usually the lab manager, who will set it up, get
people to use it, and talk to you for twenty minutes a week. And at least
four people who will use it most days.

## Before week 1: set up

For each lab, with its champion (an hour or two):

- [ ] **Where it runs.** One person: the desktop app. The whole lab: a lab
  server (the website's *Run a lab server* page, or `deploy-with-ai.md`
  with an AI assistant). Note which in your pilot notes.
- [ ] **The lab's shape.** Sign in as the first admin; the setup questions
  choose the databases, rack naming and who may change what.
- [ ] **Their data.** **Import from Excel** on each database with the
  sheets they keep now. Check a dozen records against the sheet with them.
- [ ] **Accounts.** Invite the members; give animal-facility staff the
  *care* or *facility* role; set up institution sign-in if they need it.
- [ ] **Labels.** Print cage cards (or tank and vial labels) for one rack,
  on their printer or label printer, and scan one with a phone.
- [ ] **Backups.** On a server, confirm the nightly backup ran, run a
  restore test (`docker compose exec backup restore-test.sh`), turn on the
  alerts (`deploy/README.md`, *Alerts*), and fill in the champion's copy of
  the table at the top of `deploy/RUNBOOK.md`. On a desktop, make one
  (`python scripts/dbtool.py backup`) and note where it went.
- [ ] **The agreement.** Tell them plainly: their data stays on their
  computer or server; the usage report has counts only and is sent only if
  they send it; BioManager itself sends its makers anonymous counts once a
  day (no names; the Usage report shows exactly what, and **Switch off**
  stops it); they can leave at any time: every sheet exports to Excel
  or CSV, and the database file is theirs.

## The eight weeks

| Week | The lab does | You check |
| --- | --- | --- |
| 1 | the colony (or tanks, vials) in BioManager instead of the sheet; cards on one rack | that imports were right; every Feedback note answered within a day |
| 2 | everyone adds and changes records; the calendar and Home for what is due | who hasn't signed in yet, and why |
| 3 | one experiment: a regimen, bench mode on a phone, the body-weight chart | the experiment page with them, live |
| 4 | the notebook: an experiment's record page, signing one if they want | whether the notebook replaces their paper or Word files |
| 5–8 | normal work; the old sheet only read, not written | the usage report each Monday; the top feedback fixed and released |

Ship fixes as releases during the pilot: the desktop app's **Install and
Restart**, and a server upgrade, are part of what is being tested.

## Each week

- **Monday**: the champion copies the **Usage report** (Feedback → Usage
  report → the text at the bottom) into an email to you.
- **The call** (20 minutes): what did people stop using the sheet for?
  What made someone give up? What did they have to ask a colleague? What
  would they miss if BioManager went away tomorrow?
- **Feedback notes**: the champion reads them on the Feedback page and
  marks them done; anyone can open one as a GitHub issue on the website's
  repository. Triage them there: *data loss* (fix today), *blocks work*
  (this week), *annoying* (this release), *idea* (later).

Keep one page of notes per lab: what they use, what they asked for, every
problem and when it was fixed.

## What to measure

From the usage report and the calls:

- **Weekly active people / members** (the report's *People* against
  *Members*). The target is most of the lab, most weeks.
- **Changes per area** each week, rising through weeks 1–4 and then steady.
- **Is the sheet still written to?** Ask. A lab that keeps both has not
  switched.
- **Time to find a cage and its mice**, before and after: time it once in
  week 1 with the sheet, and in week 6 with a card scanned.
- **Problems**: how many, how bad, how long each took to fix.

## Ready for 1.0 when

- [ ] Every pilot lab used it every week for the last four, with most of
  its members active and the old sheet no longer written to.
- [ ] No problem that lost or changed data without someone asking, open or
  fixed in the last four weeks.
- [ ] The top ten feedback items of each lab fixed or answered.
- [ ] At least one release installed in the field during the pilot (desktop
  update and server upgrade) with nothing lost, and one backup restored.
- [ ] Each champion would recommend it to the lab next door.
