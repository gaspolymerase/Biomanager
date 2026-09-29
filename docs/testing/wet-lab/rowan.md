# Rowan Okafor (postdoc, Reyes Lab): functional test report

## 1. Who I am and my project
I'm Rowan, the lab's protein biochemist. My project: express and purify the His6-tagged KIN45 kinase domain (~47 kDa with tag) from E. coli BL21(DE3), wild type plus a kinase-dead K→R mutant, then measure kinase activity (Km and Vmax against a peptide substrate) on the plate reader. Quinn builds the pET-28a constructs. I do expression, purification (Ni-NTA IMAC, then SEC on the ÄKTA), QC, aliquots and assays. I tested on the shared lab server (Chromium through Playwright). I used the browser only: no API calls, apart from reading my own pages' Markdown export to check what had been saved.

## 2. My two-week plan (before touching the app)
- **Day 1:** Ask Quinn for the constructs. Order Ni-NTA resin, kanamycin, HEPES, lysozyme, EDTA-free protease inhibitor and BL21(DE3). Book the shakers, sonicator, ultracentrifuge, ÄKTA, gel imager, Nanodrop and plate reader for the next two weeks.
- **Day 2:** Make the stock solutions (1 M imidazole, 5 M NaCl, 1 M Tris, 0.5 M TCEP). Transform BL21(DE3).
- **Day 3:** Expression test: IPTG 0.1 / 0.5 / 1.0 mM × 18, 25 and 37 °C, plus uninduced controls (12 cultures).
- **Day 4:** SDS-PAGE of total vs soluble fractions. Choose the conditions. Make a glycerol stock.
- **Day 5:** Scale up to 2 L (18 °C, 0.5 mM IPTG, overnight).
- **Day 6:** Harvest and store the pellets. Make the lysis, wash and elution buffers. Sonicate, clarify, run IMAC, then SDS-PAGE of the fractions.
- **Day 7:** Concentrate. Run SEC (S200 Increase 10/300). Record the fractions and peaks. SDS-PAGE.
- **Day 8:** Pool and concentrate. Measure concentration by A280 (with the extinction coefficient) and by BCA. Aliquot, flash-freeze and store at −80 with positions.
- **Day 9:** Kinase assay #1: substrate titration in triplicate on a 96-well plate, with an ADP standard curve; fit Km and Vmax.
- **Day 10:** K→R mutant prep (if the plasmid has arrived) or a second WT prep from the spare pellet. Remake the buffers. Reorder imidazole.

## 3. Day-by-day log
| Day | What I did at the bench | How I recorded it in the app (where, steps/clicks) | Worked? | Friction |
| --- | --- | --- | --- | --- |
| 1 (09-29) | Planning; asked Quinn for the construct; ordering; booking instruments | Notebook → New experiment "RO-KD-01" (typed the plan). Share: whole lab can view, Quinn can edit. Comment with @quinn. Orders → New order ×6 (11 fields each ≈ 66 entries). Calendar → New event → Booking ×17 (equipment, start, end, purpose, Save ≈ 7 actions each ≈ 120) | Yes. Overlapping booking refused: "ÄKTA pure FPLC is already booked by Rowan Okafor, Tue 06 Oct 13:30–17:30." | 17 bookings one at a time: no repeat, copy or "prep day" bundle. A booking can't be linked to the notebook page. No 25 °C shaker in the equipment list (lab setup, not the app) |
| 2 (09-30) | Stock solutions; received pLQ02 from Quinn; transformed | Reagents → New reagent ×5 (my stocks: 1 M imidazole, 5 M NaCl, 1 M Tris, 0.5 M TCEP, old BL21 cells; ~12 fields each). Plasmids → Duplicate Quinn's #9 → my aliquot #11 in Plasmid box 4 A1 (4 cell edits). Notebook: Day 2 text + plate/colony table | Yes | Quinn's plasmid appeared in Plasmids with the note "For Rowan", but I got no notification and Quinn didn't reply to the comment; I only found it by looking. A position already taken on New reagent saved the item without its box and left the New reagent dialog open |
| 3 (10-01) | Expression test, 12 cultures | Notebook: Start experiment; 12-row condition table (temperature, IPTG, OD600 at induction and harvest) pasted as a Markdown table | Yes | No "matrix / conditions" helper; I typed the 12 rows |
| 4 (10-02) | SDS-PAGE total vs soluble; picked 18 °C / 0.5 mM; glycerol stock | Notebook: /Picture ×2 (gel images), lane order written as text. Glycerol stock = second duplicate plasmid record (#13) in "Glycerol stocks box 1" A1 | Partly | The image has no lane labels; the lane legend is separate text. One plasmid record holds one tube, so one construct is now 3 records (Quinn's #9, my aliquot #11, glycerol stock #13) |
| 5 (10-05) | Scale-up 2 × 1 L | Reagents: HEPES 1 M and Kan 50 mg/mL stocks (2 more). New experiment "RO-KD-02 Prep KD-WT-P1": aim, materials and lots table, 11-step checklist, growth table | Yes | Morgan had received the orders and added them to stock, so HEPES and kanamycin showed as Reagents #33 and #32 (order → stock link worked) |
| 6 (10-06) | Harvest; buffers; sonication; IMAC; gel | Page "RO-KD Buffers": /Buffer recipe ×4 (lysis, wash, elution, SEC), each saved to the lab library. Wash and elution = Load from library → changed name, imidazole (and volume). Samples → New sample, pasted 2 names → 2 pellets into −80 A · R2 · B2 A1–A2. Prep page: IMAC gel lane table, pooled fractions, yield | Yes | Recipes: typing the first one was ~25 fields; a variant took ~6 actions. The recipe doesn't know my reagent records: no lot recorded, nothing taken out of stock |
| 7 (10-07) | SEC 2 × 500 µL, fractions, gel | Prep page: peaks written as text; fraction table (fraction, mL, mAU, lane, pooled) as a Markdown table; SEC gel image | Partly | No fraction list or chromatogram object. I typed 10 fraction rows by hand from UNICORN; no lane labels on the gel |
| 8 (10-08) | A280, BCA, 40 aliquots, −80 | A280 → mg/mL and µM worked out by hand (ε 41,370, MW 46,870). /Plate reader for BCA: pasted the 96-well grid, then 11 "Apply" operations (8 standards, 1 blank, 3 samples); result 2,481 / 2,483 / 2,318 µg/mL, R² 0.9975. Samples → New sample with 40 pasted names → KD-WT-P1-01…40 went to B1 A1–E4 in one dialog (4.6 s). Pellet 1 → status "used up" | Mostly | No protein A280 calculator. BCA fit is linear only (BCA curves bend). The box grid shows every tile as "KD-WT-P1…", so -01 and -40 look the same; it also opens on Sasha's box by default. Samples has no concentration field and no parent (source can only be Mouse/Fish/Other + text) |
| 9 (10-09) | Kinase assay #1 (ADP-Glo-type, 8 substrate concentrations × 3, no-enzyme row, ADP standards) | New experiment "RO-KD-04": planned layout as a text table. /Plate reader: pasted 50 "well value" lines, then 24 Apply operations (7 standards, blank, 8 WT triplicates, 8 no-enzyme). Results table gave µM ADP per condition. Copied 7 × 2 numbers into a /Data sheet with formula columns (=B/30, =1/A, =1/C); scatter with linear fit (Lineweaver–Burk) | Partly | The "Standard series…" tool counts down columns, so my side-by-side duplicates came out wrong (A9 = 20, A10 = 2.5) and I redid them by hand. No Michaelis–Menten fit: LB in the sheet gave Km 39 µM; the proper non-linear fit (Km 34.9 µM, kcat 17.5 min⁻¹) I did outside the app. I had to copy numbers from the plate results into the sheet by hand |
| 10 (10-12) | K→R not delivered; second WT prep from pellet 2; reorder imidazole | Replied to Quinn in the comment thread. Reagents → Imidazole → Order again (vendor and cat# filled in; quantity, price and account empty) → Orders #26. Changed my 1 M stock 500 → 315 mL by hand. "Save as template" on the prep page → New page from template → "RO-KD-03". 3 recipes from the library scaled to 500 / 500 / 250 mL, components ticked as added | Mostly | The template copies everything, including prep-1's numbers and the BCA plate readings, and the new page came out as a Note, not an Experiment. Order again filed the chemical as category "Reagent" |

## 4. Requirements coverage
| Need | Covered? (yes / partly / no) | Where in the app, or the workaround |
| --- | --- | --- |
| Request a construct from a colleague and know when it's ready | partly | Comment with @quinn on my page (Quinn is notified). Nothing tells me when Quinn adds the plasmid; I checked Plasmids myself |
| Plasmid records: construct, aliquot, glycerol stock | partly | Plasmids + Duplicate. One location per record, so 3 records for one construct |
| Order reagents; follow them; into stock on arrival | yes | Orders (requested → ordered → received), a notification each step, received → Reagents with a link back to the order |
| Reorder a reagent | partly | Order again copies vendor and catalogue number; quantity, price and account are blank if the item was never ordered in the app |
| Track reagent use (imidazole, Ni resin, IPTG) | no | Quantity is a free text/number I edit by hand. No "use 12.6 g", no link from stock solution to powder lot, no low-stock threshold |
| Buffer recipes with real amounts; scale; remake | yes | /Buffer recipe: C1V1 from stocks, mass from MW, % v/v, water remainder, ½×/2×/10×, tick as added, lab library, Load from library |
| Recipe variants (wash = lysis + imidazole) | partly | Load from library, then edit and save as a new recipe (not linked to the parent) |
| Recipe tied to reagent lots and stock | no | Lots typed in a "Materials & lots" table |
| Stock solutions as inventory | yes | Reagents, kind Buffer, my own lot codes |
| Expression-test matrix | partly | Markdown table typed by hand |
| Gel images with lane legend | partly | /Picture + a separate lane table; no labels on the image |
| Prep (lot) tracking from culture to aliquots with yield and purity | partly | All in notebook text (summary table typed by hand). Samples hold pellets and aliquots but don't link parent → child, and there are no yield or purity fields |
| Chromatography fractions, peaks, column used | partly | Markdown table + text. No fraction object, no ÄKTA CSV import, no column-use log |
| Protein concentration from A280 + ε | no | By hand. The calculators cover DNA/RNA, not protein |
| BCA standard curve | yes | /Plate reader (linear or log–log fit only) |
| Aliquots into −80 box positions | yes | Samples → New sample with a pasted list of names; they fill positions from A1 |
| Find an aliquot in the box later | partly | Box grid, but the truncated tile names hide the suffix; the table view and search work |
| 96-well plate layout | yes | Plate reader Layout tab (and the /96-well layout text grid) |
| Assay triplicates → means, CV | yes | Plate reader results (n, mean, CV %, concentration) |
| Km / Vmax fit | no | Lineweaver–Burk via formula columns and a linear fit; the real non-linear fit done outside the app |
| Book instruments, no double booking | yes | Calendar → Booking; overlaps refused with a clear message |
| Link a booking to the run / experiment | no | Wrote "booked" in the page text |
| Reuse a prep record for the next prep | partly | Save as template, but it copies all the data and loses the page type |
| Share with lab, @mention | yes | Share dialog; comments with @name |
| Link samples/reagents from a notebook page | no | @ links cover only mouse, plasmid and order; I wrote "Reagents #27" as plain text |

## 5. Tedious, repeated work
1. **Equipment bookings.** 17 in two weeks for one prep plus assays, about 7 actions each (≈120 actions). Each prep repeats the same chain: sonicator → ultracentrifuge → ÄKTA IMAC → ÄKTA SEC → gel imager → Nanodrop/plate reader. **Fix:** a saved booking bundle ("His prep, day 1") that books the whole chain relative to a start time, and a Duplicate for bookings.
2. **Plate layout roles.** 11 Apply operations for a BCA plate and 24 for the kinase plate, about 4 actions each. I'll do this 2–3 times a week. **Fix:** saved plate layouts and replicate-aware series (my duplicates sit side by side), plus "sample series" for triplicates of a titration.
3. **Moving plate results into analysis.** 14 numbers copied by hand from plate results into a data sheet every assay, plus the fit done outside the app. **Fix:** send results to a sheet, with subtraction of a control row and a Michaelis–Menten / 4PL fit.
4. **Stock solutions and consumption.** 7 stock-solution records at ~12 fields each, and after every prep the used volumes (imidazole ≈ 92–185 mL per prep) updated by hand. **Fix:** the recipe's "Made it" creates the stock-solution record (with lot and date) and takes the powder out of stock.
5. **Orders.** 6 orders × 11 fields. Order again helped only for vendor and catalogue number. **Fix:** Order again should also fill quantity, unit and grant from the item's own record; allow a basket of several orders.
6. **Prep record for the next prep.** The template copies prep-1's values (dozens of numbers and the plate readings) that I'd have to clear, and makes a Note. **Fix:** "template = structure only" (headings, tables with empty cells, blocks without data), keeping the page type.
7. **Fractions and gel lanes.** 10 SEC rows plus 13 lane rows typed per prep, twice a week. **Fix:** a fraction list imported from the ÄKTA CSV, and lane labels drawn on the gel image.

## 6. Suggested new functions
| Function | The problem it solves (from this test) | What it would do | How often it would help | Effort guess (S/M/L) |
| --- | --- | --- | --- | --- |
| Prep / lot lineage in Samples | Culture → pellet → IMAC pool → SEC pool → 40 aliquots lives only in notebook text; yield and purity typed by hand | "Derived from" link between samples; Make aliquots from a parent (n, volume, into box); per-sample concentration, volume, purity; a lot page showing the chain with total mg at each step | Every prep (1–2 a week) | M–L |
| Kinetic / non-linear fits in the data sheet | No Michaelis–Menten; I used Lineweaver–Burk and fitted outside the app | Fit models: Michaelis–Menten, 4PL (IC50), quadratic (BCA); report Km, Vmax and kcat with standard errors | Every assay | M |
| Plate results → sheet, saved plate layouts | 24 Apply operations; 14 numbers copied by hand | Save and load layouts; replicate-aware series (across or down); "subtract control row"; export results into a sheet block | 2–3 plates a week | M |
| Protein calculator | A280 → mg/mL → µM done by hand | Paste sequence or MW and ε → mg/mL and µM from A280 (path length, dilution); dilution to a target µM | Every prep and assay | S |
| Recipe ↔ inventory | Recipe amounts not tied to lots; stock not taken out; stock-solution records made by hand | Pick a component from Reagents (lot recorded); "Made it" creates the buffer/stock record and takes out the powder; recipe variants that remember their parent | Every buffer (4–6 a week) | M |
| Booking bundles and links | 17 separate bookings; not linked to the run | Book a sequence of instruments from one start time; duplicate a booking; attach a booking to a notebook page | Every prep | S–M |
| Chromatography / gel block | Fraction table and lane legend typed by hand | Import the ÄKTA CSV → trace plot, pick peaks and fractions; gel image with lane labels and a "pooled" mark | Every prep | M |
| "Structure only" templates | Template copies all data and becomes a Note | Option to clear values and block data; keep Experiment type | Weekly | S |
| @sample / @reagent / @primer links | Only mouse, plasmid and order can be linked | Same chips and backlinks for every inventory | Daily | S |
| Plasmid with several tubes | 3 records for one construct (miniprep, my aliquot, glycerol) | One plasmid, several tubes and locations | Every construct | M |
| "Ready for you" hand-off | Quinn added the plasmid "For Rowan"; I wasn't told | "Hand over / for:" field on a record that notifies the person | Each hand-off | S |

## 7. Bugs or confusing things
1. **The saved Markdown sometimes lagged behind the page (twice; cause unknown).** Page RO-KD-04: the editor showed a 4-item checklist, but the page's Markdown export (the saved copy behind export and history) had blank lines instead. It stayed blank until I next edited the page; toggling a checkbox fixed it. Page RO-KD-03: right after I reopened it, the export showed three empty ```recipe``` blocks, a repeated line, and no "Observations" section. A few minutes later it was complete again. Afterwards I opened both pages again and polled the export every 0.7 s for 7 s: it stayed correct. The live document was never damaged. Expected: the saved copy always matches the page.
2. **New reagent at an occupied position** (4 °C Fridge 1 · Shelf 1 · 3). It says "Saved …, but: … 3 already holds TRIzol-style RNA reagent", yet the reagent is saved without a box and the New reagent dialog stays open. Pressing Create again would make a duplicate. Expected: either reopen the saved item or refuse and keep the form.
3. **Standard series… on side-by-side duplicates.** I selected A9:G10 and asked for 20, ÷2, 2 replicates. It filled down columns first: A9 = 20, B9 = 20, C9 = 10 … A10 = 2.5. Expected: an option for replicates across a row.
4. **Box grid** opens on someone else's box (Sasha's RNA) rather than one of mine. The Unplaced list shows other people's samples. Tile labels cut off at "KD-WT-P1…", so my 40 aliquots look identical.
5. **Save as template** from an Experiment page gives a Note. It keeps all the data, including the plate reader's readings and layout.
6. **Order again** on the lab's imidazole (a chemical) filed the order under category "Reagent". Quantity, price and grant were blank. My first try without a quantity just stayed open (quantity is required).
7. **Recipe block:** the MW column says "needed" even when a stock concentration is given (no MW is needed then).
8. **Adding at the end of a page:** with a table or block last on the page, I couldn't reliably type or paste below it; my pasted text landed inside the table's first cell. Pasting text that starts with a new line at the end of a heading joined it into the heading ("ResultsPlate reader …").
9. Minor: the address of plasmid #9 is /plasmids/16 (an internal id). This only shows if you type addresses by hand.
10. Minor: in the Markdown export, ">" in tables comes out as "&gt;". It displays correctly in the app.

## 8. What worked well
- **Buffer recipes:** exactly what I want at the bench. Amounts from stocks (C1V1) or from MW; % v/v; water to make up; ½×/2×/10× and any volume; tick as you add; a lab library that others can load. Making the same buffers again (Day 10) took about 4 clicks per buffer.
- **BCA on the plate reader block:** paste the grid, mark wells, get the curve and per-sample concentrations with CV. Good.
- **Orders loop:** each status change reached me as a notification, and received orders appeared in Reagents with a link back to the order.
- **Samples Add many with a pasted list:** 40 aliquots into box positions A1–E4 in one dialog.
- **Booking overlaps** are refused with a clear message naming who has the instrument and when.
- **Notebook:** pasting Markdown, including tables and checklists, works; durations become timers; images upload; sharing and @mention comments work; @plasmid and @order chips resolve by number.

## 9. Evidence
- Scripts: `testing/wetlab/rowan/scripts/` (`bm.py` holds the helpers). Days: `d1*.py`, `d2.py`, `d34b.py`; orders `o2.py`; bookings `c2.py`, `c4.py`; reagents `r2.py`, `r6.py`; buffers `buf1–4.py`; prep `prep1.py`, `bca.py`, `s2–s3.py`; assay `assay2.py`, `kin*.py`; Day 10 `d10b.py`, `tpl.py`, `p2*.py`; Markdown-export checks `m5.py`, `m10–m12.py`.
- Screenshots and page text: `testing/wetlab/rowan/evidence/`:
  - bookings: `15-calendar-list`, `16-overlap`, `47-calendar-week-oct5`
  - orders: `11-order-filled`, `12-orders`, `43-order-again`
  - recipes: `26-recipe-lysis`, `27-buffers-page`, `29-recipe-ticks`, `30-recipe-library`
  - BCA: `32-bca-layout`, `33-bca-results`
  - samples: `35/36` box grids
  - kinase assay: `37-series-tool`, `38-assay-layout`, `39-assay-results`, `40-lineweaver-burk`
  - templates and prep 2: `44-newpage-templates`, `45-prep2-page`
  - full pages: `48–51`
  - simulated gels: `gel-*.png`
  - raw readings: `bca-readings.tsv`, `kinase-assay1-readings.txt`
  - page exports: `page*-export.md`
- Records I made:
  - notebook pages: 9 (RO-KD-01), 16 (Buffers), 23 (RO-KD-02), 26 (RO-KD-04), 28 (RO-KD-03)
  - plasmids: #11, #13
  - reagents: #27–31 and two more (HEPES 1 M, Kan 50 mg/mL)
  - samples: #148–189
  - orders: #10–15, #26
  - 17 bookings; 4 lab recipes
