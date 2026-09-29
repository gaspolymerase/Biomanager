# Morgan Reyes (lab manager, admin): full report, phase 1 (day 0) + phase 2 (Day 1–10)

## 1. Who I am and my project
Morgan Reyes, lab manager and the only BioManager admin of the Reyes Lab. The lab does cloning (Quinn),
cell culture, lentivirus and CRISPR (Avery), protein expression and purification (Rowan), and RNA/qPCR and
Westerns (Sasha). My "project" is keeping the lab running: accounts, storage, shared stock, ordering and budgets,
shared instruments, freezer and LN2 checks, the monthly mycoplasma test, safety and the chemical inventory,
onboarding, and answering everyone's requests.

## 2. My two-week plan (before touching the app)
- **Day 0**: set up the databases, storage map, instruments, SOPs and starting stock (phase 1, below).
- **Every day**: look at new order requests and messages; receive deliveries: check lot and expiry, put each on its shelf or in its box, tell the requester.
- **Every Thursday**: order round (one PO per vendor; each order charged to a grant) and the −80 °C freezer check (display temperature, alarm test, ice).
- **Every Friday**: LN2 dewar top-up (level before/after, litres used) and the LN2 supply delivery.
- **First Monday of the month**: mycoplasma PCR test of every line in culture; record results, quarantine positives.
- **As it happens**: reagents going low or expiring get reordered; old lots get discarded.
- **Instruments**: service visits and faults, and keeping service from clashing with bookings.
- **Day 6**: a rotation student joins, so accounts, boxes, training and the SOPs.
- **Day 9**: chemical inventory audit for the safety office: hazards, locations, waste.
- **Day 10**: spending per grant for the PI.

Day mapping (same as my colleagues): Day 1 Tue 2026-09-29 … Day 5 Mon 10-05 … Day 10 Mon 10-12. The app's real date is 2026-09-29, so every date I could type (received, ordered on, event date) uses the simulated day. Where the app stamps "today" itself, the stamp is 2026-09-29: "Saved", comment times, the guest pass end, the audit log, the Received date when an order goes to stock without one.

## 3. Day-by-day log
| Day | What I did at the bench | How I recorded it in the app (where, steps/clicks) | Worked? | Friction |
| --- | --- | --- | --- | --- |
| 0 | Survey; 2 custom databases; 34 boxes; 15 instruments; 5 SOPs + start page; import of 25 reagents, 8 antibodies, 8 oligos, 7 cell stocks, 7 plasmids; boxes handed to owners; 4 repeating chores | /setup; Add database → Custom list → Configure; New box ×34; Calendar → Manage; Notebook protocols, Edit as Markdown, Share, Save as v1; Import from Excel ×5; Racks & boxes | yes | see phase-1 notes in 5–7: no freezer hierarchy, one box at a time, personal-only templates, times lost to the All-day default |
| 1 | Configured Orders for budgets; DpnI low and ECL expiring → reordered; Sasha's urgent Nutlin-3a ordered by express; filled SYBR price | Orders → Configure: Account / grant from text to Choice (4 grants), added Needed by / Ordered on / PO # / Expected delivery, made the grant required. Reagents → cart "Order again" (2). Orders table cells (4 edits + status) | yes | "Order again" had no quantity or price (no earlier order) and category "reagent" not "enzyme". **I got no notice of the 8 requests Sasha and Rowan made that day**: I found them by opening Orders |
| 1 | Freezer/LN2/instrument log page, shared with the lab | Notebook → New page, Edit as Markdown, table per check | yes | No place in the app for equipment or freezer logs; a Markdown table in a page. The page landed in Inbox although I started it from the SOP topic: 7 pages moved one by one |
| 2 | Nutlin-3a arrived | Orders: status Received → "Add it to stock?" → Reagents (Lab common) → dialog: lot, expiry, CAS, hazard toxic, −20 °C, box, position, notes | yes, good | 1 status change + 1 offer + ~10 fields. The new record is **mine**, not Sasha's (the offer's "Personal" means the person clicking). No box for small molecules, so it went into an enzyme box |
| 3 | Thursday order round: 13 requests, 5 vendors, 5 POs | Per order: Ordered on, PO #, Expected delivery (3 cell edits × 13 = 39); then tick 13 rows → Set status Ordered (bulk). Export CSV → spreadsheet for totals per grant | yes | 39 cell edits (~40 s scripted; by hand about 10 min). No per-vendor grouping, no PO object, no totals per grant in the app |
| 3 | −80 check; qPCR lamp warning → engineer booked | Log page: Edit as Markdown, add row. Calendar → New event → Booking. First slot refused ("already booked by Sasha Varga, Tue 06 Oct 09:00–10:30"), Fri 07:00 accepted. @sasha comment | yes | Clash message is clear. No "maintenance / out of service" state, nobody is told about a service booking, no instrument log |
| 4 | Sigmund + Northbay deliveries (4) into stock; old DpnI lot → empty; LN2 top-up logged | Orders: Received → offer → dialog ×4. Reagents: status | partly | 2 of 4 saves were refused silently: the shelf positions I typed (5, 6) were taken by Rowan's stocks. The dialog stayed open with no message I could find; I had to look at the grid |
| 5 | 7 new requests incl. Avery's "TC-01 says the kit is in Reagents but I can't find one" (my error) and 3 of Quinn's notes starting "@morgan". Duplicate DpnI request cancelled with a reply; 6 urgent orders placed | Orders cells: notes + status Cancelled; per order price + 3 fields + status | yes | **@morgan in an order's notes doesn't notify me.** I overwrote Avery's per-oligo price (38) with the total (152): the app doesn't say whether Price is each or total. Vendors typed several ways ("NEB" vs "Northbay Biolabs") |
| 5 | Myco test postponed (kit late) to Day 7 | Calendar: open the repeating event → Delete this one; New event on Day 7 (untick All day) | yes | A single repeat can't be moved, only deleted and recreated; attendees aren't told |
| 6 | Myco kit + filters + sequencing arrived; TC-01 fixed and saved as v2; rotation student joins | Kit → Reagents 4 °C shelf 2. Filters: received, "Not now" (consumables have no database), location in notes. Guests → 1-week pass. Onboarding checklist page | yes | Consumables (filters, plates, cryoboxes) can't go "to stock"; neither can oligos or cell lines (only Reagents, Antibodies, Viruses are offered). The guest account name is made from the label ("guest-rotation-student-joins-day-6-s"). No invite link for a permanent member: they self-register and I approve |
| 7 | Mycoplasma results (5 cultures + controls; HEK293T P12 weak positive) | Log page: myco table. Cell lines: "Mycoplasma test" + "tested on" per row (10 cell edits; bulk can't set a custom column). @avery comment | partly | The frozen-stock database was the wrong place for a culture test result; the cultures are in Avery's personal organism database, not a lab one |
| 7 | Esp3I and Avery's 4 oligos arrived | Esp3I → Reagents Enzyme box 1 A6; oligo order received, "Not now"; the 4 oligo records already existed (Avery had marked them in stock before arrival) | yes | Order and oligo records are not linked; I checked by hand |
| 8 | 9 deliveries (4 antibodies, BL21, protease inhibitors, SYBR, ECL, Ni-NTA) into stock; qPCR plates received (consumable) | Received → offer → dialog ×9 (~12 fields each for antibodies: host, clone, clonality, dilution, applications…) | yes | 73 s scripted, ~25 min by hand. **A blank position does not take the next free one** (plasmids do): all 9 sat in their box unplaced; I set positions afterwards (9 more edits) |
| 8 | Order round 2 (LN2 standing order, cryoboxes for Avery's clones); −80 check | New order ×2 + PO fields; log row | yes | No standing / repeating order |
| 9 | Chemical inventory audit (44 records); tidy-up; LN2 delivery + top-up; qPCR back in service | Reagents table read top to bottom; new box "−20 A · Antibiotics & stock solutions"; bulk Move (took next free positions, good); old DpnI discarded + out of box; FBS location note; Export CSV for the safety office; @rowan about 2 unboxed stocks | partly | No stock-take ("seen on shelf" tick), no SDS link, GHS class or amount-per-hazard totals, no waste log. Hazard is one choice per item |
| 10 | HEK293T P8 retest negative; spending per grant | Log + Cell lines (4 edits); @avery; Orders Export CSV → totals → table in the log page | partly | Budgets only by export + spreadsheet; no grant balance. No replies to my 5 comments yet, and I'd only know by reopening the page |

## 4. Requirements coverage
| Need | Covered? | Where in the app, or the workaround |
| --- | --- | --- |
| Lab setup: databases, name, time zone, dates, member rights | yes | Setup survey |
| Primers/oligos and cell-line databases | partly | Custom lists configured by hand |
| Freezer → rack → box, shared by all databases; one freezer's contents | no | Flat boxes per database; the hierarchy only in names |
| Many boxes at once | no | 35 New-box dialogs |
| Import existing stock sheets | yes | Import from Excel (excellent) |
| See new order requests | partly | Orders → Requested chip; **no notification to the manager** |
| @mentions from order notes | no | Only notebook comments notify |
| Request → ordered → received → into stock with lot/expiry/position | yes | Orders + "Add it to stock?"; one record at a time |
| Receive oligos, cell lines, consumables into their database | no | Only Reagents/Antibodies/Viruses are offered; others by hand or not at all |
| POs, order date, expected delivery | partly | Custom columns I added; no PO grouping, no per-vendor view |
| Grant / budget tracking | partly | Account / grant as a Choice (my configure); totals only via CSV export |
| Duplicate-request detection | no | Sasha cancelled Sasha's own ECL duplicate; Quinn's DpnI I caught by eye |
| Low / expiring stock | yes | Home "Expiring & low stock" + calendar; "Order again" |
| Reorder points (e.g. reorder when < 20 rxn) | no | Status "low" set by hand |
| Standing / repeating orders (LN2) | no | New order each week, or Duplicate |
| Weekly −80 check, LN2 log, instrument maintenance log | partly | Repeating calendar events + a Markdown table page |
| Instrument service / out-of-service | partly | Booking as "SERVICE"; clash detection works; no status, no notice to users |
| Instrument training / who may book | no | Table in the onboarding page |
| Mycoplasma test tracking | partly | Calendar + custom columns in Cell lines + log table |
| Move one date of a repeating event | partly | Delete this one + new event |
| Onboarding a member | partly | Self-register + approve; guest pass; checklist page (my own) |
| Chemical inventory / safety audit | partly | Hazard + CAS + location in Reagents; CSV export; no stock-take, SDS or waste log |
| Tidy shared stock | yes | Bulk Move (next free positions), status, Lab common |
| Answer colleagues in the app | partly | Comments with @name on notebook pages; no way to message someone without a page |
| Lab-wide notebook templates | no | Templates are personal; SOPs shared as protocols |
| Lab common plasmids | no | Plasmids have no Lab common flag |

## 5. Tedious, repeated work
- **Receiving deliveries.** 18 items in two weeks, about 2 a day. Each needs a status change, the offer, and 8–12 fields (lot, expiry, box, position, storage, hazard; for antibodies host, clone, clonality, dilution, applications). The 9 on Day 8 would have been about 25 minutes by hand. If I typed no position, I also had to place the item afterwards. **What would remove it:** receive several at once, place into the next free position, and keep the details of the last lot on "Order again" (dilution, hazard, box).
- **The order round.** Twice a week, 13 and 6 orders, 4 edits each. Ordered on, PO # and Expected delivery have to be typed per row, because bulk actions only set status, box, owner or Lab common. **What would remove it:** "Place orders" on ticked rows (PO #, date, expected delivery once), and grouping by vendor.
- **Finding new requests and mentions.** Several times a day: open Orders, the Requested chip, then scan the notes for "@morgan". **What would remove it:** tell the lab manager about new requests, and make @name in any record's notes notify.
- **Freezer, LN2 and myco logs.** Weekly −80 check, weekly LN2, monthly myco of 5+ cultures. Each is 3–5 actions: open the page, Edit as Markdown, add a row, Apply. **What would remove it:** an equipment/monitoring log with a form per check, due dates and a chart.
- **Myco results into Cell lines.** Monthly, 2 fields × every line, with no bulk edit for custom columns. **What would remove it:** "Set field" for custom columns in the bulk bar.
- **Budgets.** Weekly: Export CSV, sum in a spreadsheet, paste a table back. **What would remove it:** totals per grant and per month on Orders, and a budget per grant.
- **Boxes (Day 0).** 35 dialogs, plus 11 separate "looked after by" saves.

## 6. Suggested new functions
| Function | The problem it solves (from this test) | What it would do | How often it would help | Effort |
| --- | --- | --- | --- | --- |
| Tell the lab manager about new order requests, and @mentions in any notes | 8 requests on Day 1 and 3 "@morgan" notes on Day 5 arrived without a notice | a notification (and daily digest) for new requests to admins or a chosen "orders person"; @name in any notes field notifies | daily | S |
| Place orders in one go | 39 cell edits per round | tick requested rows → "Place order": PO #, ordered on, expected delivery once; one PO per vendor; per-vendor view | 2×/week | S–M |
| Receive into any database, several at once | oligos, cell lines and consumables can't be received; 9 receipts one by one | "To stock" into any inventory (Primers, Cell lines, a Consumables list); receive several ticked orders; the next free position when blank | daily | M |
| Budgets per grant | totals only by export | Orders totals by grant, month and status; budget and balance per grant; say whether price is each or total (price × qty) | weekly, monthly report to the PI | M |
| Freezer → rack → box, shared by every database | box names carry the hierarchy; no "what's in −80 A" | a storage tree every inventory and plasmid points into; a per-freezer map | daily (finding), at freezer failure | L |
| Equipment log and status | freezer/LN2/instrument logs in a Markdown table; service booking tells nobody | per-instrument log (checks, faults, service), "out of service" that blocks bookings and tells those booked; trained-user list | weekly | M |
| Culture QC (mycoplasma) | results into frozen-stock rows by hand; cultures live in a personal database | a lab-wide test round: list cultures in culture, enter results once, flag positives, remind in a month | monthly | M |
| Duplicate-request warning | two ECL and two DpnI requests | "An open order for this catalogue # exists (#2, requested by Morgan)" when requesting | weekly | S |
| Stock-take and safety fields | audit by reading 44 rows; no SDS or waste | "Stock-take" mode ticking items as seen; SDS link, GHS classes; totals by hazard class and location; waste pickups | quarterly / on inspection | M |
| Standing orders | LN2 every week | repeat an order every N weeks | weekly | S |
| Move one date of a repeating event; notify attendees | myco test moved by delete + recreate | "Move this one"; optional notice to the lab | monthly | S |
| Invite a member by link | new members self-register, I approve | an invite link that makes an approved account with role and boxes | each new member | S |

## 7. Bugs or confusing things
1. **New event "All day" is ticked by default** while the dialog shows 09:00–10:00, so typed times were dropped (Day 0: all 4 chores became all-day). Expected: timed by default. (Day 5: I had to untick it by hand.)
2. **Refused save with no visible reason**: in a reagent's dialog, typing a taken shelf position (5, 6 on "RT · Chemical shelf") left the dialog open. I found no message, so I had to find out from the grid that Rowan's stocks sat there.
3. **A blank position doesn't take the next free one** in inventory dialogs (it does for plasmids, and bulk Move does); items sit "unplaced" in the box.
4. **"Add it to stock?" makes the stock record the clicker's** ("Personal: mine"), not the requester's: Sasha's Nutlin became Morgan's.
5. **Pages made while viewing a topic land in Inbox** (7 SOP pages; I moved each).
6. **Notebook titles sometimes not saved**: phase 1 lost 2 of 6 titles and Day 1 lost 1. Each time the title was typed about 1.5 s after the new page opened. It did not happen when I waited. Likely typed before the page script was ready; no "not saved" warning. (PLAUSIBLE)
7. Stale Home notices: 4 × "Account waiting for approval" for accounts already active, still there on Day 10.
8. Import didn't match "Position" in one sheet (mixed A1 / 1); box lists sort ignoring the "−" sign (−20, 4 °C, −80 are split); renaming a database keeps its old URL.
9. The audit log is my only "what happened" feed, and a 36-row bulk edit fills a whole screen.

## 8. What worked well
Import from Excel (matching by meaning, clear skipped-row reasons, one undoable batch). "Order again" and "Add it to stock?" carry vendor, catalogue number and lot across. The booking clash message says who has the slot and when. Bulk Move places tubes in the next free positions. Expiring and low stock show on Home and the calendar by themselves. Configure let me turn Orders into a budget-aware form in two minutes (grant choice required, PO and date columns). Protocols with numbered versions (TC-01 v2 after my kit mistake). Guest passes for a rotation student are quick. Colleagues could use everything I set up: Sasha cancelled their own duplicate ECL after seeing mine, and Rowan and Sasha filled boxes I had made.

## 9. Evidence
- Scripts: testing/wetlab/morgan/scripts/: s01–s36 are phase 1 and p2_* are phase 2. Helpers: bm.py, cfg.py, boxes.py, imp.py, orders.py, cal.py, nb.py, logrow.py, place.py. CSVs are in csv/ and the SOP Markdown is in md/.
- Screenshots: testing/wetlab/morgan/evidence/. Phase 1 is 00–31, cfg-* and look-*. Phase 2 is p2-01 to p2-13: orders configure, reorder dialog, order round, stock offer, booking clash, comment, guest pass, myco log.
- Exports: orders-export-day3.csv, orders-export-day10.csv, chemical-inventory-day9.csv.
- In the app: notebook topic "Reyes Lab · shared SOPs". It holds the SOPs (TC-01 is now v2), "Equipment & freezer log (Reyes Lab)" (−80, LN2, instruments, myco, spending) and "Onboarding checklist".

### Phase 1 notes (day 0), in short
Setup survey quick; no cell lines, primers, enzymes or kits in it. Two custom lists took ~35 fields each. 34 boxes one dialog at a time, with no freezer/rack levels. 15 instruments with name, room and colour only. Notebook templates are personal only. Plasmids can't be lab common. Imports were very good but had no "Lab common" target, so I bulk-set it afterwards. Full phase-1 notes: testing/wetlab/morgan/PHASE1.md; what exists: testing/wetlab/setup-done.md.
