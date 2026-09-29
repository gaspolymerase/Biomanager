# Avery Lindqvist (Reyes Lab): cell culture, lentivirus and CRISPR clones in BioManager

## 1. Who I am and my project
I'm Avery Lindqvist, a grad student in the Reyes Lab. My project is an RLX1 knockout in U2OS and A549 cells, made with lentiCRISPRv2: SpCas9, puromycin resistance, and guides sg1 (exon 2) and sg2 (exon 4). Quinn cloned the dual-guide vector, pLQ01 (Plasmids #8).

I run two arms at once:
- **U2OS pilot arm:** already at the clone stage. 32 single-cell clones from an earlier pilot virus were picked on 2026-09-28.
- **A549 arm, plus a second U2OS pool:** starting now with new virus.

I keep 4–10 vessels going at any time. Sasha runs the Western blots.

## 2. My two-week plan (written before touching the app)
- **Day 1:**
  - Thaw U2OS P12, A549 P10 and 293T P8 from LN2.
  - Book TC hood 1 for two weeks.
  - Ask Quinn for the vector.
  - Order the genotyping primers.
- **Day 2:** Change medium after thawing. Record the 32 pilot clones and the pilot virus lot after the fact.
- **Day 3:**
  - Split all flasks, with counts on the cell counter.
  - Seed a puromycin kill curve in a 24-well plate (0–3 µg/mL).
- **Day 4:**
  - Seed 293T, 2 × 10 cm at 5 × 10^6 each.
  - Expand 24 clones into 12-well plates and pellet the other half for gDNA.
- **Day 5:**
  - PEI transfection of pLQ01 with pMDLg/pRRE, pRSV-Rev and pMD2.G (10 : 5 : 2.5 : 2.5 µg, PEI 3:1).
  - Monthly myco supernatants.
  - Read the kill curve.
- **Day 6:** Medium change at 16 h. Myco results. Send the clone PCRs for Sanger sequencing.
- **Day 7:**
  - 48 h harvest: filter 0.45 µm, 10 × 1 mL to −80 B.
  - Transduce A549 and U2OS at MOI about 0.3, 1 and 3.
  - Call the clones from TIDE.
- **Day 8:**
  - 72 h harvest (second lot).
  - Start puromycin: A549 at 1.5 µg/mL, U2OS at 1 µg/mL.
  - Make lysates of the KO candidates for Sasha.
- **Day 9:** Freeze down 6 KO clones × 3 vials, plus 4 vials each of parental U2OS and A549, into the −80 transfer box.
- **Day 10:**
  - Move the vials to LN2.
  - Discard the clones that aren't KO.
  - Routine splits.
  - Titer the virus.
  - Plan single-cell cloning of the A549 pool (after Day 10).

## 3. Day-by-day log
"Actions" means clicks plus fields filled, counted in my scripts. Where the app let me set a date, I used the simulated date.

| Day | What I did at the bench | How I recorded it in the app (where, steps/clicks) | Worked? | Friction |
| --- | --- | --- | --- | --- |
| 0/1 | Read the guide | The guide covers *frozen* cell stocks (a Custom list) but has nothing for live cultures. The README tip says organism databases fit cell lines. Built **Avery cultures** from Add database → Custom organism, "Just me": 12 vocabulary words, age unit "Passages", 10 capabilities, then 10 custom fields (passage number, medium, vessel, confluence, split ratio, count, viability, virus lot/MOI, puromycin, myco) and 2 schedule rules (split every 3 d, feed every 2 d). | yes | About 60 fields and choices before the first flask. A newcomer wouldn't find this: the guide has no word on cell culture. |
| 1 | Thawed 3 vials | Cell lines sheet: edited QTY in place (5→4, 3→2, 6→5) and added a note to each row (4 actions per vial). Avery cultures: 1 incubator, 3 cell lines (5 fields each), 3 flasks (11 fields each), 3 cultures (14 fields each). | yes | About 30 actions per thawed line. No "take a vial" button: nothing records who took it except my note (the audit log is admin-only). A flask and its culture are two records with the same data. |
| 1 | Asked Quinn for the vector; warned Sasha about the Western | Project page in Notebook (Blank page, Edit as Markdown); Share with Quinn and Sasha; two comments with @quinn / @sasha. Sasha replied in the thread within minutes. Quinn had already made pLQ01 (seen in Plasmids). | yes | A mention is a notice, not a request with a status. I track "did it arrive" myself with a checkbox. `@quinn` typed into page text is plain text, not a mention. |
| 1 | Ordered primers, filters and a myco kit | Primers & oligos: 4 × New oligo (13 fields each). Orders: 3 × New order (about 10 fields). Morgan marked them received, and I got a notification for each. | yes | Length isn't computed from the sequence. Oligo status has no "ordered" state, so it said "in stock" before the oligos arrived. |
| 1 | Booked TC hood 1 for 10 days | Calendar → New event → Booking: 10 dialogs × 6 actions = 60 | yes | Bookings can't repeat (events can). |
| 1 | Started the virus experiment | LV-01 → Start an experiment from it: a checklist with timers. Filled the materials table with plasmid lots and amounts (Edit as Markdown). | yes | The page header says "started 08:00 PM", the body says "Started 16:00". |
| 2 | Medium change on 3 flasks; checked 32 clones | 3 culture dialogs to record confluence and a note (5 actions each), plus Last serviced typed in 5 flask rows (2 each): 22 actions. Pilot virus lot recorded after the fact (1 dialog, Made from = #4). 32 clones: 1 batch (SCC-U1), 2 plates, then **Add many** "U2OS-C01" × 24 and "U2OS-C25" × 8 (2 dialogs, about 15 fields each). | yes | **The feed pushed the split back:** both rules count from the flask's one "Last serviced" date, so the split moved from 10-02 to 10-03. Passage number, confluence and the other custom fields are **read-only in the sheet**, so every change needs the dialog. |
| 3 | Split U2OS 1:4, A549 1:5, 293T 1:3 with counts; seeded the kill curve | 3 culture dialogs (9 actions each: passage, vessel, confluence, ratio, count, viability, note) = 27, plus 5 × Last serviced = 10. Kill-curve plate: 1 flask and 2 cultures. Cell counter booked for 15 min. | yes | **37 actions to passage 3 flasks.** Old values are overwritten, so there is **no passage history** (I kept it as note lines). "Done" on the Schedule tab stamps the real date, not the date I passaged. |
| 4 | Seeded 293T into 2 dishes; moved 24 clones to 12-well; 24 gDNA pellets | 293T passage: 11 actions. 2 new dishes: 2 flasks + 2 cultures = 50 actions. 2 new 12-well plates (22), then select 12 → Move twice (24 ticks, 4 clicks). Samples → Add many with 24 pasted names, Source = Avery cultures, box B3 from A1 (placed A1–C6 automatically): 1 dialog. | mostly | Moving doesn't change the clones' Vessel field (still "24-well"), and there's no bulk "set field". The source clone can't be set per row in Add many, so linking each pellet to its clone took **1 dialog per sample (about 7 s × 24)**. I did 3. The source then shows as text, not a link. |
| 5 | Transfected 293T; myco supernatants; kill-curve readout | 2 culture dialogs with the transfection note (10 actions). Materials table added to AL-LV-01 (plasmid #, lot, µg). Kill curve as a Markdown table on a new page. Myco sampling noted on 3 cultures, and Last serviced set on 9 vessels = 30 actions. | yes | No place for a plate result (per-well puromycin score) except a notebook table. |
| 6 | Medium change at 16 h; myco negative; Sanger order | 10 actions for the 2 dishes; 15 for myco on 3 cultures; 1 order (service) | yes | The monthly myco result has to go to each culture *and* to the Cell lines inventory by hand. No single myco form. |
| 7 | 48 h harvest; transduced A549/U2OS; TIDE calls on 24 clones | New virus with **How many 10**: 10 aliquot records placed −80 B · R1 · B1 A2→B2, Made from = pLQ01 #8 (1 dialog, 17 actions). 2 plates + 2 cultures (46 actions). **Bulk Record genotype**: 5 groups (KO −1/+1, KO −7/−7, het, in-frame, WT) for 24 clones, 44 actions. | yes, good | Zygosity choices are mouse ones (het, hom, wt, hemi, carrier, trans-het). No "biallelic / compound het / in-frame", and no way to attach the Sanger trace or TIDE file. |
| 8 | 72 h harvest (8 aliquots); retired dishes; started puromycin; 8 lysates for Sasha | Virus How many 8 (17 actions) + 2 status changes; puromycin on 2 cultures (14); Samples Add many into Sasha's lysate box H1–H8 (12); comment to Sasha with positions | yes | My second @Sasha mention silently became plain text "@Sas" (see Bugs). Sasha's Day 9 page said "not in the app yet": we worked on different real clocks. |
| 9 | Froze 26 vials | Cell lines → Add many × 3 (18 KO vials, 4 U2OS, 4 A549), about 20 fields each, into the −80 cryo transfer box (placed A1… automatically). A warning said "Made from plasmid" wasn't a plasmid and was kept as typed. Clones kept "growing" (bulk Set status). | yes | Vials are made by retyping what the culture record already has (passage, myco, medium). There's no "freeze down from this culture". The Cryo tab in my culture database works per cell line, not per clone, so I didn't use it (it would be a second copy). |
| 10 | Vials to LN2; discarded 18 clones; routine splits; titer; myco alert | Cell lines: search, shift-click, Move to box (next free positions) × 2 = 12 actions for 26 vials. Bulk Set status "discarded" on 18 clones (20). Routine split of 3 flasks = 30. Titer typed into 10 aliquot rows. **Morgan @mentioned me: my 293T at P12 was weak myco-positive on Day 7.** I marked 293T-1 contaminated and put "ON HOLD" in the notes of all 18 aliquots of LV-AL-02/-03, one at a time. | partly | After moving the vials to LN2, "Stored at" still said −80 °C (the move doesn't change it; no bulk set field). The virus lots have no link to their producer cells, so I tracked back to them by memory. Titer and hold had to be typed per aliquot (10 + 18 edits). |

## 4. Requirements coverage
| Need | Covered? (yes / partly / no) | Where in the app, or the workaround |
| --- | --- | --- |
| Live cultures (flask, passage, confluence, medium) | partly | Only by building my own organism database. No preset; custom fields can't be edited in the sheet. |
| Passage history per culture | no | Old values are overwritten; I kept a note line per passage (the audit log is admin-only). |
| Split / feed reminders | partly | Schedule rules on the flask show on the Schedule tab, the Calendar and Home → Tracks (not Classic). Feed and split share one "Last serviced" date; Done can't be backdated. |
| Cell counts / viability | partly | Number fields, typed by hand. No counter import, no cells/mL → seeding calculator linked to the culture (the notebook has a separate cells calculator). |
| Puromycin selection-day reminders | no | Nothing tied to the culture. Would need a Calendar to-do, or an Experiments regimen (not tried). |
| Kill curve / MOI plate results | partly | Notebook Markdown table or data sheet only. |
| Thaw / take a vial from LN2 | partly | Edit QTY and note in the Cell lines sheet. No who/when; status doesn't change to low/last vial by itself. |
| Who took the last vial | no | Only my free-text note; the audit log is admin-only. |
| Freeze-down vials with passage, date, box position, myco | yes (tedious) | Cell lines → Add many (paste names), automatic positions, bulk Move to LN2. Everything retyped from the culture. |
| 20–40 single-cell clones through expansion | partly | Add many with consecutive IDs and bulk Move are good. No well position per clone, no plate map, and Vessel can't be set in bulk. |
| Clone genotyping | yes | Bulk Record genotype; Genotyping tab. Zygosity words and file attachments don't suit CRISPR. |
| Samples (gDNA, lysates) linked to clones | partly | Samples Add many + Source "Avery cultures": one source for the whole batch, then one dialog per sample. Shown as text, not a link. |
| Virus lots ↔ plasmid | yes | Made from = plasmid #; the plasmid's Storage tab lists "Made from this plasmid" (every aliquot listed separately). |
| Virus lot ↔ packaging plasmids, producer cells, target cells | no | Notes only. Couldn't trace the myco-positive 293T to its lots in the app. |
| Aliquots with positions | yes | New virus → How many N places them side by side in the −80 box. |
| Titer or hold on all aliquots of a lot | partly | Inline edit per aliquot; no bulk set field. |
| Request a plasmid from Quinn / Western from Sasha | partly | Shared page + @mention comments (they arrived, Sasha replied). No request object with status. |
| Monthly myco test | partly | Lab repeating event + TC-01 protocol. Results typed into each culture and inventory row. |
| Book TC hoods / cell counter | yes (tedious) | Calendar booking with a conflict check; no repeats. |
| Protocol → experiment record (LV-01) | yes | Start an experiment from it: checklist, timers, materials table. |
| Orders for oligos, filters, kit, sequencing | yes | New order; notified when received. |

## 5. Tedious, repeated work
1. **Routine passaging.** 3–6 maintenance flasks every 2–3 days, about 2–3 times a week, so 10–15 passages a week. Each one is about 9 actions in the culture dialog plus 2 for the flask's Last serviced, which is 11 actions and 2 page loads. Measured: 37 actions for 3 flasks. At 6 flasks that is about 70 actions per split day.
   - *Fix:* a Passage action on selected flasks. Enter the ratio and count once; it bumps the passage, logs the event with its date, and resets the split timer.
2. **Medium changes.** 2–3 a week, 2 actions per vessel, but each one also postpones the split reminder.
   - *Fix:* a Fed button that resets only the feed rule.
3. **New vessel when splitting into plates or dishes.** About 25 actions per vessel (flask + culture records). 4 times this fortnight.
   - *Fix:* "Split into…" makes the child vessels and cultures from the parent.
4. **Linking samples to their clone.** 24 gDNA pellets plus 8 lysates, 1 dialog each (about 7 s).
   - *Fix:* Add many from selected cultures, where each sample gets its own source.
5. **Freezing vials.** 3 dialogs × 20 fields retyping passage, myco and medium from the culture. Every freeze-down.
   - *Fix:* "Freeze down" from a culture, pre-filled.
6. **Per-aliquot edits.** 10 titer edits + 18 "on hold" notes for 2 lots.
   - *Fix:* lot-level fields, or a bulk Set field.
7. **Hood bookings.** 10 dialogs for one fortnight.
   - *Fix:* repeating bookings (weekdays).
8. **Myco results.** For each line in culture, the result goes into the culture and the inventory row.
   - *Fix:* a monthly myco sheet that lists every culture and writes both.

## 6. Suggested new functions
| Function | The problem it solves (from this test) | What it would do | How often it would help | Effort guess (S/M/L) |
| --- | --- | --- | --- | --- |
| Cell-culture preset with Passage / Feed actions | Passaging needs 11 actions per flask and keeps no history; there is no preset at all | "Cell culture" ready-made database (flask, passage, medium, confluence, count). Select flasks → **Passage** (ratio, count, viability, optional new vessel) or **Fed**. Each writes a dated event in a per-culture timeline, bumps the passage, and resets only its own timer. | 10–15 times a week per person | L |
| Editable custom fields in the sheet + bulk "Set field" (all inventories and organisms) | Vessel, puromycin, Stored at and titer can't be changed in place or in bulk | Custom fields edit in the cell like the built-in ones; the select bar gets "Set field…" | Daily | M |
| Per-rule "last done" and backdated Done | A feed postpones the split; Done stamps today | Each schedule rule keeps its own last-done date; Done asks for the date (default today) | Every feed/split | S–M |
| Freeze down from a culture / Take a vial | Vials retyped by hand; nobody knows who took the last vial | From a culture: N vials in Cell lines, pre-filled and linked, placed in the box. On a vial: **Take**, which lowers QTY, records who and when, sets low / last vial, and tells the owner. | Weekly (take), each freeze-down | M |
| Clone plates | 32 clones with no wells or plate map; Vessel stayed "24-well" after moving | A 24- or 96-well plate as a housing with a well per clone, a plate map (colour by genotype), and "move to 12-well plate, same layout" | Every cloning round (20–40 clones) | M |
| Sample Add many from selected records | 24 gDNA pellets needed 24 dialogs to link to their clones | Tick cultures → "Make samples": one sample each, source linked (clickable), placed in the box | Each genotyping or Western round | S |
| Virus lot with aliquots, several plasmids and producer cells | Titer and holds per aliquot; no link to packaging plasmids or the 293T that made it; the myco trace-back was manual | Lot record: transfer + packaging plasmids, producer culture, target cultures (the transduction); aliquots underneath; titer set once for the lot | Each virus prep; every contamination scare | M |
| Requests between lab members | Quinn's vector and Sasha's Western tracked by my own checkbox | "Request from @person" with status (asked → accepted → delivered), linked to the record that fulfils it (plasmid #8, WB page) | Weekly | M |
| Repeating equipment bookings | 10 hood booking dialogs | Repeats on bookings (every weekday until…), with the conflict check per date | Weekly | S |
| CRISPR genotype calls | Mouse zygosity words; no trace or TIDE upload | Configurable call words (biallelic frameshift, in-frame, het, WT), allele 1 and 2 fields, file attachment per call | Each clone round | S |
| Monthly myco form | Results retyped per culture and inventory row | Lists every live culture; tick negative/positive once; writes the culture, the matching stock rows and the date; a positive flags the lots made from that line | Monthly | S–M |
| Cell counter via API → culture | Counts typed by hand | A documented recipe or token scope to post count and viability to a culture (the API can "change a vial"; I didn't try it for organisms) | Every split | S |

## 7. Bugs or confusing things
1. **Custom organism fields are read-only in the sheet.**
   - Steps: Avery cultures → Cultures; click the Passage number cell.
   - What happened: it's plain text, not an input.
   - Expected: editable like Status or Born.
2. **Feed and split share one anchor.**
   - Steps: two rules on housing, both counting from "Last serviced". Set Last serviced for the feed.
   - What happened: the split moved 3 days later too (10-02 → 10-03).
   - Expected: each rule has its own last-done date. Also, the Rules table's "Recurring" column was empty although I ticked "Falls due again after completion".
3. **Age unit "Passages" still shows days** ("0d" in the Age column). Passage isn't tracked by the system; I had to add a field.
4. **The @mention picker only takes a mouse click.**
   - Steps: type "@Sas" and press Enter.
   - What happened: a newline was added and the comment posted "@Sas" as plain text, with no notice to Sasha.
   - Expected: Enter or Tab picks the highlighted person, or a warning that the mention didn't resolve.
5. **Moving vials to another box leaves "Stored at" wrong.** A vial moved from the −80 transfer box to an LN2 box still says −80 °C.
6. **Two times on one notebook page.** The experiment header says "started today 08:00 PM" while the inserted body line says "Started: 2026-09-29 16:00". My browser was on UTC and the lab is on New York time.
7. **Plasmid Storage → "Made from this plasmid" lists every aliquot** (18 lines for 2 lots) instead of grouping by lot.
8. **Sample Source shows as text only** ("Avery cultures · U2OS-C01"), with no link to the culture. It can't be set per row in Add many.
9. **Home → Classic doesn't show my culture split/feed dues.** Only Tracks, the Calendar and the Schedule tab do.
10. **Oligo statuses have no "ordered"**, so a primer shows "in stock" before it arrives. Cell lines "low" / "last vial" isn't set from QTY.
11. **The guide says nothing about live cell culture.** The Cell lines database is frozen stock only, and "use an organism database" for cells is a single README tip.

## 8. What worked well
- **Add many:** consecutive IDs (32 clones in 2 dialogs); pasted names placed side by side in freezer boxes (24 pellets, 26 vials).
- **Bulk actions:** Move to box/flask filling the next free positions, Set status, and especially **Record genotype** for 24 clones in 5 groups.
- **Virus aliquots:** New virus → How many placed 10 aliquots in the −80 box. Made from links the plasmid, and the plasmid lists what was made from it.
- **Custom organism database:** a member can build a working culture database with schedules, genotyping, pedigree ("Derived from" line) and batches, private to me.
- **Working with the others:** @mentions and page sharing reached Sasha, who answered in the thread. Morgan's myco alert reached me the same way. Orders notified me when they were received. Hood bookings refuse overlaps.
- **Protocols:** LV-01 → Start an experiment gave a checklist with timers, and the Markdown editing was reliable.

## 9. Evidence
- Scripts: `testing/wetlab/avery/scripts/` (`bm.py` helpers; `s*.py` exploration and setup; `d2*`–`d10*` are the working days; `fin*.py` are the final checks).
- Screenshots: `testing/wetlab/avery/evidence/`. Key ones:
  - `05-newdb-filled.png`, `07-configured.png`: building the culture database.
  - `14-cultures-day1.png`, `d2-schedule.png`: feed pushing the split back.
  - `d2-addmany.png`, `d2-clones.png`: 32 clones.
  - `38-bulkbar.png`, `d7-genotyping.png`: bulk genotype.
  - `d7-virus-dialog.png`, `d10-virus-titer.png`, `fin-plasmid-storage.png`: virus aliquots and plasmid links.
  - `d4-samples-addmany.png`, `s46-sample-grid.png`: gDNA pellets.
  - `d9-cell-lines-frozen.png`, `d10-cells-ln2.png`: freeze-down and move to LN2.
  - `28-comments-posted.png`, `d10-comment-sasha3.png`: requests to Quinn and Sasha.
  - `36-bookings.png`, `37-cal-list.png`: hood bookings.
  - `22-lv-exp.png`, `lv-exp-md.txt`: the virus experiment page.
- Records I made:
  - **Avery cultures** (personal database): about 40 cultures, 12 flasks and plates, 4 cell lines, 1 batch, 24 genotype calls.
  - Lentivirus #1–#19 (3 lots).
  - Cell lines #8–#33 (26 vials).
  - Samples #190–#213 (gDNA pellets) and #214–#221 (lysates).
  - Primers & oligos #33–#36.
  - Orders #20–#22 and #25.
  - Notebook pages 12 (AL-LV-01), 14 (project plan and requests), 27 (kill curve).
  - 11 bookings.
