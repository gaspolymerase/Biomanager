# Function test: a wet lab's everyday work in BioManager

Can a wet-lab-heavy lab plan and record its everyday experiments in
BioManager? Five testers played five people in one fictional lab, the Reyes
Lab. They used one shared lab server (PostgreSQL, as a lab would run it) for
two simulated working weeks, at the same time, through the browser. Each one
planned the real bench work for their project first, then recorded it as it
happened. They worked with each other only through the app. They noted what the app
covered, what it didn't, what they had to do over and over, and what should
be built.

The testers were AI agents (Claude Code) with the same brief
([BRIEF.md](wet-lab/BRIEF.md)). The five full reports are in
[wet-lab/](wet-lab/), and the people are fictional. The code tested is the
1.0 candidate, with the fixes in [TESTING.md](../TESTING.md). What was
changed afterwards is under [What was done for 1.0](#what-was-done-for-10).

| Person | Role and project | Report |
| --- | --- | --- |
| **Morgan** | Lab manager and admin: set the lab up on day 0, then orders, stock, freezers, instruments, mycoplasma tests, onboarding, safety, budgets | [morgan.md](wet-lab/morgan.md) |
| **Quinn** | Postdoc, cloning: three HiFi constructs and a mutagenesis, primers, colony PCR, minipreps, sequencing, hand-over | [quinn.md](wet-lab/quinn.md) |
| **Avery** | Grad student, cell culture: thawing and passaging, lentivirus, a CRISPR knockout, 32 single-cell clones, genotyping, freezing down | [avery.md](wet-lab/avery.md) |
| **Rowan** | Postdoc, protein: His-tag kinase expression tests, a 2 L prep, IMAC and SEC, aliquots, buffers, a kinase assay with Km | [rowan.md](wet-lab/rowan.md) |
| **Sasha** | Grad student, RNA and Westerns: 36 treated samples through RNA, cDNA, 9 qPCR plates and ΔΔCq, BCA and Westerns, plus Westerns for Avery | [sasha.md](wet-lab/sasha.md) |

Over the two weeks the lab made:

- about 220 sample tubes in freezer boxes;
- 26 frozen cell vials, 40 protein aliquots and 19 virus aliquots;
- 36 primers and oligos;
- about 25 orders, 18 of them received into stock;
- about 55 instrument bookings;
- about 30 notebook pages, with protocols, buffer recipes, plate readings, data sheets and statistics.

## The answer

**Mostly yes.** Every tester could plan and record their two weeks in
BioManager, and would keep using it.

**Where it covers everything a wet lab needs:**
- Stock and where it is (freezer boxes, positions, lots, expiry).
- Ordering from request to stock.
- Instrument booking.
- The notebook, with protocols and versions, calculators, buffer recipes, data sheets with stats, and plate readings.
- Working together: sharing, @mentions, notices.

**Where it falls short:**
- **Following material through an experiment.** Nothing links a sample to what is made from it: RNA to cDNA to qPCR plate, culture to pellet to aliquots, colony to miniprep to sequencing to glycerol stock. Every tester held the chain together with tube names and notes.
- **Getting instrument numbers into records.** Concentrations, purity, Cq values and fractions had no field to go in, so they went into notes as text.
- **The every-2–3-days routine of cell culture**, which has no home of its own.
- **Sequence and kinetics work.** The app has no primer Tm, no primer binding on the map, no sequencing import, no non-linear fits and no chromatography import.

## What each person could do

| | Covered | Partly | Not covered |
| --- | --- | --- | --- |
| **Lab manager** | Lab setup, importing old stock sheets, low and expiring stock, booking clashes, bulk moves | Order rounds (typed row by row), receiving (reagents, antibodies, viruses only), budgets (by export), chore logs (as notebook tables) | Notices of new requests, a shared freezer → rack → box structure, making many boxes at once, equipment logs and out-of-service, standing orders, stock-take and safety data sheets |
| **Cloning** | Primer and plasmid records, plasmid maps from GenBank or FASTA, the Cloning page's digest and ligation calculator, orders, bookings, hand-over | Reaction setups (retyped per page), primer pairs (two records) | Tm, length and GC from a sequence; primer binding on the map; in-silico assembly; tracking colony → miniprep → sequencing → glycerol stock; miniprep yield on the tube; sequencing results |
| **Cell culture** | Clones by the dozen (Add many), bulk genotype calls, freezing vials into boxes and moving them to LN2, virus aliquots linked to their plasmid | Live cultures (only by building a personal database: about 60 fields and choices), split and feed reminders (one shared date), requests to colleagues (comments, no status) | Passage history, "take a vial" and who took the last one, freeze down from a culture, a virus lot with its packaging plasmids and producer cells, clone plates |
| **Protein** | Buffer recipes (from stocks or molecular weight, scaled, ticked off, lab library), BCA on the plate-reader block, aliquots into box positions, orders to stock | Prep records (notebook text only), plate layouts (many clicks), templates for the next prep (they copy all the data) | Prep lineage with yields, a protein A280 calculator, Michaelis–Menten or other non-linear fits, recipes linked to reagent lots and taking them out of stock, fraction lists and gel lane labels |
| **RNA and Westerns** | 36 tubes at once with positions, master-mix and loading calculators, ΔΔCq and statistics in data sheets, sharing | Nanodrop and BCA values (only as text), the qPCR block (one reference gene, one control sample), antibody lots (retyped per blot) | Sample → RNA → cDNA → plate links, a qPCR plate layout, number columns for concentration and purity, links from a page to an antibody or sample, tracking a reused diluted primary |

## What worked well (said by several testers)

- **Import from Excel.** It matched columns by meaning, found boxes by name, said
  which rows it couldn't place and why, and made one batch that can be undone.
- **Add many.** With a pasted list of names it filled the next free box positions: 12–40 tubes, 32 clones
  or 26 vials in one or two dialogs.
- **Bulk actions**: move to the next free positions, set status, record
  genotype for 24 clones at once, labels.
- **Booking** refuses an overlap and names who has the instrument and when.
- **The orders loop**: a notice at every step, received orders become stock
  with their lot, and expiring or low stock shows up on Home by itself.
- **The notebook's tools**: buffer recipes, master-mix, seeding, molarity and
  ligation calculators, data sheets with formulas, plots and proper stats,
  the plate-reader block, protocols with versions, and Start an experiment
  from a protocol.
- **Working as a lab**: sharing, @mention comments and notices worked. For
  example, Sasha answered Avery within the session, and Sasha cancelled a
  duplicate order after seeing Morgan's.

## Tedious, repeated work

| Chore | Who | How often | Steps each time | What would remove it |
| --- | --- | --- | --- | --- |
| Booking a chain of instruments | Sasha 21, Rowan 17, Avery 10 bookings | every experiment | about 6–7 actions per booking | repeating bookings, duplicate a booking, a booking bundle ("His prep day 1") |
| Plate layouts on the plate-reader block | Sasha, Rowan | 2–3 plates a week | 272 actions for one BCA plate; 11–24 role assignments | saved layouts, fill a named series across or down in duplicate, paste a layout |
| qPCR plate layouts and grouping results | Sasha | 9 plates in two weeks | an 8 × 12 table typed per plate; 252 sample names renamed per time point | a qPCR plate block that maps samples × targets × replicates and reads the export by well |
| Passaging cells | Avery | 10–15 times a week | about 11 actions per flask, no history kept | Passage and Fed actions on selected flasks that log the date and reset only their own reminder |
| Receiving deliveries into stock | Morgan | about 2 a day | status, the offer, then 8–12 fields; one at a time | receive several at once, into any database, into the next free position |
| The order round | Morgan | twice a week | 3 fields typed per order (39 edits for 13 orders) | "Place order" on ticked rows: PO number, date and delivery once; grouped by vendor |
| Instrument numbers into records | Sasha, Rowan, Quinn | every extraction, BCA, miniprep, prep | pasted into notes, then again into sheets | number fields for concentration and purity on samples and plasmids, and "write results back to these tubes" |
| Setting one field on many records | Avery, Morgan | daily | one dialog per record for custom fields (titer on 10 aliquots, "on hold" on 18, myco on every line) | custom fields editable in the sheet, and "Set field" in the bulk bar |
| Linking samples to what they came from | Avery (32), Sasha (108), Rowan (40) | every extraction, RT, lysis, aliquoting | one dialog per sample, or only by naming | "Make from these": one child per selected parent, linked both ways |
| Freeing positions of used-up tubes | Sasha | every batch | a second bulk action | used up or discarded frees the position |
| Primers: Tm and length, F/R pairs | Quinn, Avery | every oligo | 2 numbers typed; 2 records per pair | work them out from the sequence; "Add primer pair" |
| Lab setup: boxes and custom databases | Morgan, Avery | at setup, every new rack | 35 box dialogs; 21 columns; about 60 fields for a culture database | "add a rack of N boxes"; presets for primers, cell lines and cell culture |

## Suggested new functions, most valuable first

Asked by = how many of the five testers ran into the problem.

### Quick wins (small, used every day or week)

| Function | Asked by | Why |
| --- | --- | --- |
| **Notices that reach the right person**: tell the lab manager about new order requests; @name in any record's notes notifies; Enter picks the highlighted person in the @ list; a checklist line with @name becomes their to-do; a "for: @person" hand-off on a record | Morgan, Avery, Sasha, Rowan | requests were found by looking; one @mention silently didn't send |
| **Custom fields editable in the sheet, and "Set field" in the bulk bar** | Avery, Morgan, Sasha | every change to a custom column needed a dialog per record |
| **@links to every kind of record** (antibody, reagent, sample, primer, cell line), with "used in" on the record | Sasha, Rowan | lots were retyped per page and once got wrong; only plasmids, orders and mice can be linked now |
| **Repeating and duplicated bookings** | Sasha, Rowan, Avery | 48 booking dialogs across three people |
| **Positions that look after themselves**: used up frees the position; a blank position takes the next free one in every dialog; moving updates "stored at"; a taken position is refused with a clear message | Sasha, Morgan, Avery, Rowan | full-looking boxes, unplaced deliveries, silent refusals |
| **"Already on order" warning; Order again fills quantity, price and grant** | Sasha, Morgan, Rowan | two duplicate orders in two weeks |
| **Number fields for results on Samples and plasmid tubes** (concentration, unit, A260/280, A260/230, volume) | Sasha, Rowan, Quinn | Nanodrop, BCA and miniprep values ended up in notes |
| **Primer tools**: length, Tm and GC from the sequence; "Add primer pair" | Quinn, Avery, Morgan | typed by hand for every oligo |
| **Protein calculator**: A280 with the extinction coefficient → mg/mL and µM | Rowan | done by hand every prep |
| **Templates that keep structure only and keep the page type; lab-wide templates** | Rowan, Morgan, Quinn | a template copied a whole prep's data and became a Note; templates are personal only |
| **Setup helpers**: "add a rack of N boxes"; presets for Primers & oligos, Cell lines and Cell culture; a Lab common option in imports and on plasmids | Morgan, Avery | about 35 dialogs and 80 fields at setup |
| **Schedules**: each reminder keeps its own last-done date, and Done can be backdated | Avery | a medium change pushed the split back |
| **Calendar**: "first Monday of the month"; move one date of a repeating event | Morgan | the mycoplasma test was moved by deleting and recreating it |
| **Cryo labels**: choose the fields; wrap to two lines | Sasha | the name and position were cut off |

### Bigger pieces (a week or two each)

| Function | Asked by | What it would do |
| --- | --- | --- |
| **Sample lineage** | Sasha, Rowan, Avery, Quinn | a "made from" link on samples, filled by "make RNA/cDNA/aliquots from these" (one child per parent, next box positions, parent marked used up if wanted); a lot page showing the chain with the amount at each step |
| **Ordering for the lab manager** | Morgan | place orders on ticked rows with one PO per vendor; receive several into any database; totals and a balance per grant; price each vs total; standing orders |
| **Plate tools** | Sasha, Rowan | saved plate layouts; series across or down, in replicates; results into a data sheet or back onto the tubes; quadratic, 4PL and Michaelis–Menten fits with errors |
| **qPCR plate and analysis** | Sasha | a plate map of samples × targets × replicates with no-template and no-RT roles; read the export by well; average technical replicates; the geometric mean of several reference genes; a control group; ΔΔCq per biological replicate |
| **Recipes linked to stock** | Rowan | pick each component's reagent and lot; "Made it" creates the stock-solution record and takes the powder out of stock; variants remember their parent recipe |
| **Cell-stock actions** | Avery | "Freeze down" from a culture (pre-filled vials in the box); "Take a vial" (who and when, sets low or last vial, tells the owner) |
| **Virus lots** | Avery | a lot with its transfer and packaging plasmids, producer culture and titer, with the aliquots under it, so a contaminated producer line shows which lots it made |
| **Requests between members** | Avery, Rowan | "Request from @person" with a status (asked → accepted → delivered), linked to what fulfils it |
| **Lab-manager logs** | Morgan, Avery | an equipment log with an out-of-service state that blocks bookings and tells those booked; a monthly mycoplasma round over every culture; a stock-take mode, safety data sheet links and a waste log |
| **Clone plates** | Avery | a 24- or 96-well plate as housing, one well per clone, a plate map coloured by genotype |

### Large

| Function | Asked by | What it would do |
| --- | --- | --- |
| **Cell culture** | Avery | a ready-made culture database: flasks, passage, medium, confluence and counts, with Passage and Fed on selected flasks writing a dated history |
| **Clone and screen tracker** | Quinn, Rowan | colonies for a construct, each carrying colony PCR, miniprep yield, sequencing verdict and a status, with "promote" to the verified plasmid or glycerol stock; one plasmid with several tubes |
| **Freezers as places** | Morgan | freezer → rack → box shared by every database, and a map of one freezer's contents |
| **Sequence tools** | Quinn | primer binding sites and amplicon size on the plasmid map; import and alignment of sequencing reads |
| **Chromatography and gels** | Rowan | import the ÄKTA trace, pick peaks and fractions; lane labels on a gel image |

## Bugs and confusing things found

| # | What | Seen by | Where |
| --- | --- | --- | --- |
| 1 | A notebook title typed right after a new page opens is sometimes lost (5 pages) | Morgan, Sasha | Notebook, new page, then Edit as Markdown |
| 2 | The page's saved copy (export, history) lagged behind the editor twice, then caught up | Rowan | Notebook |
| 3 | New event starts with "All day" ticked while showing 09:00–10:00, so typed times are dropped | Morgan | Calendar |
| 4 | A new reagent at a taken position is saved without its box and the dialog stays open, with no clear message | Morgan, Rowan | Reagents |
| 5 | Used-up tubes keep their box positions | Sasha | Samples |
| 6 | Order again doesn't warn about an open order for the same item | Sasha, Morgan | Reagents → Orders |
| 7 | In the @ list, Enter posts the typed text ("@Sas") instead of picking the person, and nobody is told | Avery | Comments |
| 8 | Moving a vial to another box leaves "Stored at" as it was | Avery | Cell lines |
| 9 | Custom organism fields can't be edited in the sheet; feed and split reminders share one date; Done can't be backdated; Age shows days with the unit set to Passages | Avery | Organism databases |
| 10 | The qPCR block counts no-template and no-RT wells as samples (one showed a 52× change) | Sasha | Notebook qPCR block |
| 11 | "Standard series" fills side-by-side duplicates down the columns | Rowan | Plate-reader block |
| 12 | Save as template turns an Experiment into a Note and keeps all its data | Rowan | Notebook |
| 13 | Home kept four "Account waiting for approval" notices for accounts already active | Morgan | Home |
| 14 | Pages started while a topic is open land in Inbox | Morgan | Notebook |
| 15 | Cryo labels and box tiles cut off names and positions | Sasha, Rowan | Labels, box grid |
| 16 | Search for "S20" ranked another person's records before exact name prefixes | Sasha | Search |
| 17 | An experiment page shows two different start times (the browser's zone and the lab's) | Avery, Sasha | Notebook |
| 18 | Smaller: "Position" not matched on one import; box lists sort −20, 4 °C, −80 apart; a renamed database keeps its old address; plasmid "#N" differs from its address; "CDNA" capitalised; oligos have no "ordered" status; time points like "48 h" become timers | several | |

Not confirmed: sharing a page with one person seemed not to register for
Quinn, but four person-to-person shares by the others were saved, so it is
not counted as a bug.

## What was done for 1.0

After the test, for 1.0:

- **Bugs fixed:** 1, 3, 4, 5, 6, 7, 8, 9, 10, 12 and the cryo labels in 15.
  Still open: 2 (not reproduced), 11, 13, 14, 16, 17, the box tiles in 15,
  and the small ones in 18 (oligos now have an *ordered* status).
- **Quick wins done:** every row of the quick-wins table, with these left
  out: the "for: @person" hand-off on a record, and a Cell culture preset
  (Primers & oligos and Cell lines are presets now). @name tasks go to
  to-dos from any page with ⋯ → *Send @name tasks as to-dos*, not from
  every checklist line as it is typed.
- **Bigger pieces and large** are for after 1.0, sample lineage first.

## How it was done, and its limits

- **Setup.** A frozen copy of the 1.0 candidate ran with gunicorn (3 workers)
  on PostgreSQL 16. The lab manager set the lab up on day 0 through Lab setup, as
  a new lab would, then the four researchers and the lab manager worked at
  the same time.
- **How the testers worked.** They clicked and typed in Chromium through
  Playwright, like a person would. The API was used only where a lab would
  script an instrument (one plate-reader upload). They counted the actions
  for repeated work.
- **Time.** Two working weeks were acted out in an afternoon. Dates that can be
  typed use the simulated day, and dates the app stamps itself use the real
  one. So reminders arriving day by day, and replies that take days, were not
  really seen.
- **Data.** Instrument data (Nanodrop, plate reader, qPCR exports, gels) was
  made up to look real. The sequences are placeholders.
- **Scope.** A wet-lab-heavy lab only: no animal colony and no dry-lab or
  imaging work.
