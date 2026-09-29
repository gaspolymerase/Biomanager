# Sasha Varga: RNA/qPCR and Western work in BioManager

## 1. Who I am and my project
I'm Sasha Varga, a grad student in the Reyes Lab (username sasha). I test how the MDM2 inhibitor nutlin-3a changes gene expression and protein levels in A549 cells, which have wild-type p53. The design is 4 doses (vehicle 0.1% DMSO, 1, 5 and 10 µM) × 3 time points (6, 24, 48 h) × biological triplicates, which gives 36 samples. From each sample I make RNA, then cDNA, then SYBR qPCR: 4 targets (CDKN1A, MDM2, BAX, GDF15) and 2 reference genes (GAPDH, ACTB). I also make a RIPA lysate from each sample for BCA and Westerns (p53, p21, MDM2, β-actin). I run Westerns for Avery's RLX1 knockout clones when Avery asks.

## 2. My two-week plan (before touching the app)
- **Day 1 (Tue 09-29):** Plan the sample matrix and tube labels (S01–S36 plus a suffix: -Tz TRIzol, -R RNA, -c cDNA, -L lysate). Order nutlin-3a, the p53/p21/MDM2 antibodies, SYBR (it will run short) and qPCR plates; ECL expires 10-20. Order the missing target primers. Passage A549 and seed 36 wells (2.5 × 10⁵ per well of a 6-well plate). Book the TC hood, cell counter, Nanodrop, thermocycler, plate reader, qPCR cycler ×9 and gel imager ×3.
- **Day 2:** Treat at 09:00, harvest 6 h at 15:00. Each well's pellet is split: half goes into TRIzol, half into RIPA, and both go to −80 °C.
- **Day 3:** Harvest 24 h.
- **Day 4:** Harvest 48 h. TRIzol RNA extraction of all 36, Nanodrop (A260/280 and 260/230). Passage the stock flask.
- **Day 5:** DNase, then cDNA from 1 µg of RNA (input normalised per sample), plus 3 no-RT controls. BCA with a BSA standard curve on the plate reader.
- **Days 6–8:** qPCR. The cycler takes 96 wells, so it is 9 plates, 3 per day: 12 samples × 2 genes × triplicates, plus NTC and no-RT. Master mix is N+10%. Export Cq values and compute ΔΔCq with both reference genes. Westerns: 20 µg per lane, 4–20% gel, wet transfer, membrane cut into strips, primaries overnight, ECL on the imager, ImageJ band quantification.
- **Day 9:** Western for Avery (Cas9, RLX1, β-actin), reusing the diluted β-actin.
- **Day 10:** Reprobe for MDM2; write up results. All tubes stay in the −80 boxes with their positions. Update stock (SYBR low; antibody volumes used).

## 3. Day-by-day log
| Day | What I did at the bench | How I recorded it in the app (where, steps/clicks) | Worked? | Friction |
| --- | --- | --- | --- | --- |
| 1 | Planned the matrix; passaged A549, seeded 36 wells | Notebook → New topic → New page → New experiment "NUT-01 plan…". A data sheet with 36 rows (sample, label, dose, time, rep, plate, well), the **Cell count & seeding**, **Molarity** and **Dilution** calculators, and a materials/lots list. Written with ⋯ → Edit as Markdown | yes | The 36-row sheet had to be typed or pasted; nothing generates a design from "4 doses × 3 times × 3 reps". "6, 24, 48 h" in prose became ⏱ timers. I can't @-link the cell line, reagents or antibodies (only plasmids and orders) |
| 1 | Ordered nutlin-3a, anti-p53/p21/MDM2, SYBR, ECL, plates | Orders → New order ×5 (~11 fields each); Reagents → cart **Order again** for SYBR and ECL | yes | **Order again** made a duplicate ECL order: Morgan already had one open (#2), and neither the reagent row nor the dialog said so. I cancelled mine (#4) |
| 1 | 8 target primers (CDKN1A, MDM2, BAX, GDF15 F/R) | Primers & oligos → Import from Excel (CSV), all 15 columns matched → Preview → Import 8 | yes, very good | Pair/partner is plain text, not a link. Length and Tm typed by hand, not worked out from the sequence |
| 1 | Booked 21 instrument slots for 2 weeks | Calendar → New event → Booking ×21 (equipment, start, end, purpose; ~6 actions each) | yes, no clashes | ~126 actions. No "same slot on days X, Y, Z" and no copy of a booking |
| 1 | Avery asked (comment with @sasha) for an RLX1 Western | Bell → notification → Avery's page → Comments → Reply with @avery. Also ordered anti-RLX1 (none in Antibodies) | yes | Avery's checklist line "- [ ] @sasha Western… due 2026-10-09" in a Note page did not become a to-do for me (the guide says only meeting action items do) |
| 2–4 | Harvests: 12 TRIzol + 12 RIPA tubes per day | Samples → **Add many**, paste 12 names, set type/source/date/amount/box once; position A1 on Day 2, left blank on Days 3–4 (it took the next free cell: B4, C7…). 6 runs, ~12 fields each | yes, very good | Source is only Mouse/Fish/Other, so the cell line is free text. Dose/time/rep live only in the name. No per-row values in Add many |
| 4 | RNA extraction, Nanodrop of 36 | Samples → Import from Excel with the Nanodrop CSV (conc, 260/280, 260/230) → 36 RNA tubes in E1–H9 | partly | Samples has no concentration or purity columns, and only Morgan can add them, so all 3 values went **into the notes as text**. No link from RNA to its TRIzol tube (typed "from S01-Tz" in notes) |
| 4 | TRIzol tubes gone | Search "homogenate" → select all → Set status **used up**, then a second pass → Move → **Unplace** | yes | **Used-up tubes kept their box positions** (box showed 72/81 full) until I unplaced them: 2 bulk actions every time |
| 4 | Labels for the RNA tubes | Select → **Labels** → Cryo tube 1.28 × 0.5 in → Show | partly | The cryo label cuts the name to "S01-R · V-…" and the place to "−80 A · R1 · B1 · RN…". The group and position (the useful parts) are lost, and there is no date |
| 5 | DNase + cDNA; 1 µg input normalised | Notebook page "RNA → DNase → cDNA". A data sheet of the 36 Nanodrop values with formula columns `=1000/C` (µL RNA) and `=8-F` (water). **Master mix** calculator: DNase 39 rxn +10%, RT 36 +10%, no-RT 3 | yes | Nanodrop values pasted a second time (they are only in the notes). Page title lost (see bugs) |
| 5 | cDNA tubes | Samples → Add many ×2 (36 cDNA A1–D9; noRT-1..3 E1–E3) | yes | Type list shows "CDNA". Parent RNA again only as text |
| 5 | BCA of 36 lysates | New page with a **Plate reader** block: pasted the reader grid → Fill the plate; Layout: 8 standard pairs, blank pair, 36 sample pairs (select 2 wells, choose role, type name and dilution 5, Apply); Results | yes | **272 UI actions** for one plate. There is no "fill these 36 names down the plate" and no layout paste. Fit is linear or log–log only: BCA curves bend, R² 0.985, and my samples read ~7% high. The results table has no copy/export |
| 5 | Put concentrations on the tubes | API token (Settings → API tokens, Read and change), script `api_bca.py` PATCHed 36 lysates' Amount to "55 µL · 2.74 mg/mL (BCA 2026-10-05)" | yes | The script needed the values re-exported by hand from the block. There is no concentration field to put them in |
| 5 | Loading 20 µg per lane | Data sheet on the BCA page: `=round(20/(B/1000),1)` µL lysate, RIPA to 15 µL | yes | Concentrations copied by hand from the plate results. Negative RIPA volumes for dilute samples are not flagged |
| 6–8 | qPCR 9 plates (3 per time point) | 3 notebook pages from the **qPCR** page type: master mix (42 rxn +10%), plate layout as a Markdown 8×12 table, run checklist. Pasted the cycler CSV into the **qPCR ΔΔCt** block → Read → reference GAPDH (auto-picked) → control sample | partly | See §5/§7: one reference gene only. The control is one sample, not a group. NTC/no-RT are counted as samples (no-RT "fold 52×" wrecks the plot scale). For per-group results I rewrote 252 sample names per time point to their group in Excel, which then mixes biological and technical replicates (Welch on n = 9, 15+ "replicates span" warnings) |
| 9 | ΔΔCq done properly (2 refs, n = 3) | Results page: one **Data sheet** per target × time with Cq means per biological replicate, `=C-(D+E)/2` and `=pow(2,-(F-vehicle mean))`, plot + stats (one-way ANOVA, Welch vs V with Holm) | yes | Tech-rep means worked out outside. Vehicle mean typed into the formula (formulas can't average "rows where Group = V"). I did 6 of 12 sheets; the rest would go to Excel |
| 6–8 | WB1: gel, transfer, strips, primaries, ECL, ImageJ | Western blot page type: lanes (µg, µL), steps, antibody table (antibody, record, dilution, lot, diluted-primary tube and use count), band-intensity sheet with `=C/F` normalisation, stats | yes | Antibody lots are typed in the page. I first wrote wrong lots, because Morgan created the antibody records (from my orders) only after the blot, then corrected them. No @antibody link. Images stay on the lab drive |
| 8 | SYBR running low; β-actin used | Reagents: SYBR quantity 1.2, status **low** (it appeared on Home under Expiring & low). Antibodies #1: 100 → 96 µL, note about the diluted "actin 1:5000 #1" | yes | Manual subtraction. Nowhere to track a diluted working primary and how often it was reused |
| 9 | Avery's Western | New Western page, Share → Avery can edit ("Shared. They have been told.") | partly | Avery's lysates never appeared in Samples during my session, so the lanes are placeholders |
| 10 | Log, dates | Plan page Log (passages P13→P14→P15→P16, per-day notes); page date field set to the simulated day on 8 pages; Start experiment | yes | Passages have no home (Cell lines holds frozen vials, not flasks in culture). **Start experiment** stamps real time, not Day 1 |

## 4. Requirements coverage
| Need | Covered? | Where in the app, or the workaround |
| --- | --- | --- |
| Plan a 36-sample matrix and labels | partly | Notebook data sheet, typed or pasted. No design generator |
| Create 36+ tubes at once with positions | yes | Samples → Add many (paste names; next free cells) or Import from Excel |
| Tube labels (cryo) | partly | Labels → Cryo tube: name and place truncated |
| Per-tube values (RNA conc, 260/280, 260/230, protein mg/mL) | partly | Only as text in the notes/Amount. Columns need the admin (Configure) |
| Lineage sample → RNA → cDNA → plate → result | no | Naming convention (S20-Tz/-R/-c/-L) plus notes. Global search on "N5-24h-R2" finds all 4 tubes, which works only because of the naming |
| Free the box positions of used tubes | partly | Manual bulk Unplace after "used up" |
| Master mix N+10% | yes | Notebook Master mix calculator |
| Normalised RNA input / protein loading | yes | Data-sheet formula columns |
| qPCR plate layout | no | Markdown table. The page type's hint says "plate layout" but there is no layout block; the Plate reader block is for readings |
| Cq import and ΔΔCq | partly | qPCR block: 1 reference gene, control = 1 sample, controls not excluded. Proper analysis in data sheets |
| 2 reference genes (geometric mean) | no | Data-sheet formula |
| Stats across biological replicates | yes | Data-sheet stats (ANOVA, Welch, Holm), plot |
| BCA standard curve from plate reader | yes (with limits) | Plate reader block; linear/log–log only; 272 actions for the layout |
| Push instrument results to records | partly | API (PATCH items) works; there is nothing to receive it but text fields |
| Band intensities → normalised values | yes | Data sheet + formulas + stats |
| Antibody: which, dilution, lot | partly | Antibodies database has dilution and lot; the notebook can't link to it, so lots are retyped |
| Diluted primary reuse | no | Free text in the WB page and the antibody note |
| Book shared instruments | yes | Calendar → Booking (21 made, no conflicts) |
| Order when low / expiring | yes | Orders, Order again, Home "Expiring & low". No "already on order" warning |
| Requests from colleagues | partly | @mentions in comments reach me. A checklist @sasha in a normal page doesn't make a to-do |
| Cell culture passages | no | Notebook text |
| Share work with a colleague | yes | Share → person → can edit; they are notified |

## 5. Tedious, repeated work
- **qPCR plate layouts**: 9 plates, 96 wells each, typed as Markdown tables (8×12 cells). Nothing ties the layout to the export or to the samples. **Fix:** a qPCR plate block (drag samples × targets × replicates onto wells, NTC/no-RT roles) that reads the Cq export by well.
- **Rewriting sample names to groups for ΔΔCq**: 252 rows per time point, 3 times. Then technical triplicates averaged by hand, 12 per sheet × 12 sheets. **Fix:** let the qPCR block take a sample → group map, average technical replicates first, use several references (geometric mean), and exclude NTC/no-RT.
- **Plate reader layout**: 272 UI actions for one BCA plate (45 select + role + name + Apply cycles). Every BCA, every week. **Fix:** "Samples: fill these names down/across from B3 in duplicate" or paste a layout grid.
- **Instrument values into records**: 36 Nanodrop rows went into notes; 36 BCA values went into the Amount text by an API script; the same values were re-pasted into sheets twice. **Fix:** number columns on Samples (conc, unit, purity) plus a "write these results back to the tubes" button on plate/sheet blocks.
- **Freeing positions**: every time tubes are used up, 2 bulk actions (status, then Unplace). **Fix:** used up / discarded clears the position (or offers to).
- **Bookings**: 21 dialogs × ~6 actions = ~126 actions. **Fix:** a booking repeat on chosen days, or duplicate a booking.
- **Antibody lots and use**: 6 antibodies retyped with lots per blot; manual volume subtraction; diluted-primary reuse tracked in prose. **Fix:** an @antibody (and @reagent, @sample) mention that pulls lot/dilution, and a "working dilution" child record with use count and made-on date.
- **Lineage in notes**: 108 tubes each with "from Sxx-…" typed or templated. **Fix:** a "made from" sample link, filled by Add many as "one child per selected parent".

## 6. Suggested new functions
| Function | The problem it solves (from this test) | What it would do | How often it would help | Effort guess (S/M/L) |
| --- | --- | --- | --- | --- |
| Derive samples from samples | RNA → cDNA → plate had no links; 108 tubes linked by name only | Select 36 RNA tubes → "Make cDNA from these": one child each, same number, next box positions, "Made from" link both ways, parent optionally marked used up and unplaced | every extraction/RT/lysis (3–4× per experiment) | M |
| qPCR plate + analysis block | Layouts typed by hand; 1 reference gene; control is one sample; NTC/no-RT counted | Plate map of samples × targets × reps (roles NTC/no-RT), read the export by well, tech-rep means, geometric mean of references, control = group, ΔΔCq per biological replicate, stats on n = bio reps, export | every qPCR run (9 plates this fortnight) | L |
| Number columns for results on Samples (conc, 260/280, 260/230, mg/mL) + import into them | Nanodrop/BCA ended as text in notes | A preset "nucleic acid" / "protein" field group on Samples; import and API fill it; sortable, usable in formulas | each extraction and BCA | S |
| Plate reader layout fill + 4PL/quadratic fit | 272 actions per BCA; linear fit biased ~7% | Name a series across N well pairs in one step; paste a layout grid; quadratic and 4PL fits; results → sheet or tubes | weekly | M |
| @antibody / @reagent / @sample mentions | Lots retyped (and wrong); no link from a blot to the tube used | Mentions for every inventory, hover showing lot/dilution/expiry, backlinks on the record ("used in WB1") | every experiment page | S–M |
| Working dilutions of antibodies | Reusing diluted primary tracked in prose | A child "working dilution" (dilution, buffer, made on, uses, discard after N uses/days) that shows on the antibody | every Western | S |
| "Already on order" and used-up clears position | Duplicate ECL order; full box after used-up | Warn on Order again when an open order exists; show "on order #2" on the reagent; free positions on used up | weekly | S |
| Experiment design generator | 36-row matrix typed | "Factors: dose 4 × time 3 × rep 3" → the sheet, names and tube labels | each new experiment | S |
| Cryo labels with chosen fields and wrapping | Name and position truncated | Choose fields (name, short ID, date, position), 2-line wrap, smaller type | every batch of tubes | S |
| Checklist @name in any page becomes a to-do | Avery's request line didn't reach my to-dos | Same as meeting action items, for any page | weekly | S |

## 7. Bugs or confusing things
1. **Page title lost.** Notebook → New page (Blank page or qPCR), type the title, Tab, then ⋯ → Edit as Markdown → Apply within ~3 s. 2 of my 8 pages were saved as "Untitled page" and "qPCR" (the same bug Morgan saw). Expected: the typed title is kept. I retyped both.
2. **qPCR ΔΔCt block counts controls as samples.** When I paste an export with NTC/no-RT rows (the Task column says NTC), the no-RT rows get "fold change 52.2" and the bar plot's axis goes to 60, so the real 1–10× bars look flat. Expected: NTC/no-RT (by Task column or name) excluded or shown as QC only.
3. **Used-up samples keep their position.** Set 36 tubes to "used up" and the box grid still shows them, "72 of 81 filled". Expected: position freed (the record keeps where it was).
4. **Order again doesn't warn about an open order.** Reagents → ECL → cart made order #4 while Morgan's #2 for the same item was still open. Expected: "ECL is already on order (#2, requested by morgan)".
5. **Cryo tube labels** truncate the sample name and the box/position with "…".
6. **Global search ranking.** Ctrl K "S20" lists 10 of Rowan's samples (probably "S200" in their notes) and none of my S20-* tubes. "S20-c" or "N5-24h-R2" works. Expected: exact name prefixes first.
7. **Grouped qPCR warnings.** When groups pool bio reps, "replicates span > 0.5 cycles" fires 15+ times: it is biology, not pipetting.
8. Durations in plain text ("48 h") get ⏱ timers even when they are time points, not steps.
9. Samples "Type" list shows **"CDNA"** (the lab's "cDNA" capitalised).
10. **Start experiment** stamps the real time, and the page date field (which can be set) is separate; easy to end up with two different dates.
11. The **qPCR page type's** hint says "Master mix, plate layout, ΔΔCt analysis", but it has no plate layout.

## 8. What worked well
- **Add many with pasted names** plus "next free position" is excellent for 12–36 tubes at once. **Import from Excel** matched every primer and Nanodrop column, with a clear preview and an undoable batch.
- **Bulk select** (search → select all → status / move / labels) and one-click **Labels** with a cryo size.
- The notebook's **Master mix** (N+10%), **Seeding**, **Molarity/Dilution** calculators and **data sheets with formula columns, plots and proper stats** (ANOVA, Welch with Holm) covered the real maths. My per-biological-replicate ΔΔCq with two references was done entirely in the app.
- The **Plate reader block** read a pasted reader grid, fitted the curve and flagged CV.
- The **qPCR block** read a real-looking export with header lines untouched, auto-picked GAPDH and flagged the outlier replicate.
- Orders flowed fast. Notifications told me when things were ordered or received, and received orders became stock records (Morgan did that, with lots). Home picked up low SYBR and expiring ECL.
- **Comments with @mentions** and **Share** made working with Avery and Morgan easy. The **API** was straightforward for a plate-reader script.

## 9. Evidence
- **Scripts:** `testing/wetlab/sasha/scripts/`. `bm.py`, `nb.py`, `samples.py` are helpers; `data.py`, `bca.py`, `qpcr.py` simulate the instrument data; `s01`–`s53` are the steps; `api_bca.py` is the instrument script; `csv/` holds the primer, Nanodrop and qPCR exports. The API token and browser session files were deleted after the test.
- **Screenshots:** `testing/wetlab/sasha/evidence/`:
  - 07 orders
  - 10 primer import
  - 13 calendar
  - 16 and 50 plan page
  - 19–23 Add many and bulk
  - 24 cryo labels
  - 27–28 comments to Avery
  - 29 BCA plate layout and results
  - 30 loading sheet
  - 32–33 box grid before and after unplacing
  - 34 qPCR blocks
  - 36 ΔΔCq sheet with stats
  - 39 Western quantification
  - 40 @ menu (plasmids and orders only)
  - 46 sharing
  - 52 search
- **Records in the app:**
  - Samples #1–111 (sasha)
  - Primers #9–16
  - Orders #3–9 and #16
  - 21 bookings
  - Notebook topic "Sasha · NUT-01…", pages 11, 15, 17, 18, 20, 21, 22, 24, 25
