# BioManager wet-lab test — Quinn Adeyemi (molecular cloning)

## 1. Who I am and my project
I'm Quinn, a postdoc in the Reyes Lab doing molecular cloning for colleagues. Over two
weeks I build three constructs by HiFi/Gibson + Golden Gate: (A) a dual-sgRNA
lentiCRISPRv2 KO vector for Avery, (B) a pET-28a His6-tagged ~45 kDa kinase domain
("KIN45") for Rowan, (C) a pcDNA3.1 N-FLAG cDNA for overexpression; plus one
site-directed K→R kinase-dead mutant. The work is primer/oligo design, gradient PCRs,
gels, gel extraction, DpnI, assembly, transformation, colony PCR of 8–12 colonies each,
miniprep + Nanodrop, diagnostic digest, Sanger, pick correct clones, glycerol stocks,
hand off plasmids. Realistic failures included (assembly A gave no colonies → redo).

## 2. My two-week plan (before touching the app)
- Days 1–2: design all primers/sgRNA/SDM oligos; order oligos + missing enzymes (Esp3I,
  DpnI is low) by the Thursday deadline; book thermocycler/gel imager/Nanodrop.
- Days 2–4: gradient PCR of inserts B & C; anneal sgRNA duplexes; gel + gel-extract; DpnI;
  HiFi (B,C) + Golden Gate (A); transform Stbl3 (lenti) / DH5α (B,C); plate.
- Days 4–6: colony PCR 8–12/construct; overnight cultures of positives; miniprep + Nanodrop;
  diagnostic digest; submit Sanger.
- Days 6–8: read Sanger, align to reference, pick correct clones; redo whatever failed
  (assembly A did); SDM on B to make kinase-dead.
- Days 8–10: re-verify redo/SDM; glycerol stocks; hand pLQ01→Avery, pLQ02(+KD)→Rowan.

## 3. Day-by-day log
| Day | At the bench | Recorded in app (where, steps) | Worked? | Friction |
| --- | --- | --- | --- | --- |
| 1 | Designed 6 cloning/seq primers | Primers & oligos → New oligo ×6; each: name, kind, seq, target, **length**, **Tm**, conc, scale, partner, box, position, notes (~13 fields) | yes | Length & Tm are **manual number fields** — the app never computes them from the sequence. No pair-entry: F and R are two separate records cross-referenced by hand. |
| 1 | Designed 4 sgRNA duplex oligos + 2 SDM primers | New oligo ×6 (sgRNA kind, no Tm) | yes | sgRNA oligos have no meaningful Tm; field just left blank. Still 13 fields each. |
| 1 | Created the 3 target constructs | Plasmids → New plasmid ×3 (name, backbone, insert, resistance, box, notes) | yes | Fine, but a construct is a *design*; there's no field for "how many colonies / which clone / concentration". |
| 1 | Wrote the cloning experiment page | Notebook → new **Cloning** page: digest table, ligation calculator, transformation timers pre-built | yes | Rich template, but "Colonies & screening" is an **empty heading** — no structured colony tracker. |
| 1 | Ordered Esp3I, DpnI top-up, Sanger service | Orders → New order ×3 (item, category, vendor, cat#, qty, **grant account**, needed-by, notes with @morgan) | yes | @morgan in notes is just text; the requester (me) is notified on status change, not the mentioned admin. |
| 2 | Booked thermocycler(gradient)+gel imager+Nanodrop | Calendar → New event → Booking ×3 (instrument, start, end, purpose) | yes | Overlapping booking **correctly refused**, naming who holds it and when. |
| 2–3 | Loaded assembled sequence to check map | Plasmid pLQ02 → paste FASTA → 900 bp interactive map | yes | Map is view/annotate only; features must be drawn by hand; no primer-binding overlay from my Primers DB, no assembly simulation. |
| 4 | Colony PCR, 10 colonies/construct | Free text in the cloning page (no colony table) | partly | Had to type colony list by hand; nothing links colony 3 → its miniprep tube → its Sanger read → its glycerol stock. |
| 4–5 | Minipreps + Nanodrop yields | Nowhere structured: yield/A260:280 go in plasmid **notes** | partly | Plasmid record has no concentration / 260:280 / yield fields. |
| 5–6 | Sanger back, align, pick clone 3 | Recorded verdict in notes; made verified clone a **duplicate** plasmid record → renamed → moved to Glycerol stocks box | partly | No .ab1 import or alignment; duplicate carries the sequence, which helps for the glycerol tube. |
| 6 | Assembly A failed → redo; SDM K→R | Daily-log/notes narrative; new oligos already in place | yes | Failure captured only as prose. |
| 8–10 | Glycerol stocks; handover | Shared cloning page lab-wide (can view); Rowan created their own aliquot record of pLQ02 in their box | yes | Handover = share page + colleague makes their own tube record; works but manual. |

## 4. Requirements coverage
| Need | Covered? | Where / workaround |
| --- | --- | --- |
| Store primers/oligos with sequence, target, box | yes | Primers & oligos DB (rich fields, box grid, autocomplete) |
| Compute primer Tm / length / GC | **no** | Manual number fields; I computed elsewhere and typed them |
| Primer pairs (F/R) as a unit | partly | "Pair / partner" text field cross-refs two separate records |
| sgRNA oligos | yes | "sgRNA oligo" kind; own box |
| Plasmid maps + sequence | yes | Paste/upload GenBank/FASTA/SnapGene, interactive OVE map |
| Annotate features / show where a primer binds | partly | Manual annotation in editor; **no** auto primer-binding from Primers DB |
| In-silico assembly / digest / cut-site check | **no** | Not present; did it in external tool |
| Reaction setup (digest, PCR master mix, ligation) | partly | Cloning-page tables + built-in calculators (good), but re-entered per page |
| Track 8–12 colonies → miniprep → Sanger → glycerol | **no** | No colony/clone tracker; free text + duplicated plasmid records |
| Miniprep concentration / A260:280 / yield | **no** | Goes in plasmid notes |
| Sanger results (.ab1, alignment, pass/fail per clone) | **no** | Notes only |
| Order reagents/enzymes/oligos/service from lab manager | yes | Orders with grant accounts, statuses, board |
| Book thermocycler / gel imager / Nanodrop | yes | Calendar bookings; overlap refused with holder+time |
| Freezer/box positions for tubes | yes | Box grid per DB; glycerol-stock box |
| Handover to Avery/Rowan | yes | Share page; colleague makes own aliquot record |
| Record failures / redos | partly | Free text only |

## 5. Tedious, repeated work
1. **Typing Tm and length for every oligo** — 12 oligos this project, and I re-run this every
   cloning round. 2 hand-entered numbers per oligo that the app already has the sequence to
   compute. Fix: auto-fill length from the sequence and offer a Tm (with a chosen method) the
   moment a sequence is entered.
2. **Entering F/R primers as two independent records** — every PCR = 2 oligo records with
   duplicated target/scale/box, then a manual "partner" cross-link. ~6 pairs here. Fix:
   "Add primer pair" that takes both sequences and shares the common fields.
3. **Reaction setups re-typed per experiment** — the digest/PCR/ligation tables live in each
   notebook page; I re-enter volumes each of ~6 cloning pages/round. Fix: save a reaction
   table as a reusable block / lab template (guide says "Save as template" is personal only).
4. **Colony→miniprep→Sanger→glycerol has no thread** — 8–12 colonies × 3 constructs = ~30
   colonies to track by hand, matching "colony 3" to a miniprep tube label to a Sanger read to
   a glycerol position, entirely in prose. This is the single biggest gap and the most
   error-prone. Fix: a clone/screen tracker (below).
5. **One plasmid record per physical tube/aliquot/glycerol stock** — Duplicate helps (carries
   sequence) but I still rename + rebox each; and a construct's identity (the map) is entangled
   with a single box position, so N tubes of one construct = N near-identical records.

## 6. Suggested new functions (most valuable first)
| Function | Problem it solves (from this test) | What it would do | How often it helps | Effort |
| --- | --- | --- | --- | --- |
| **Clone/screen tracker** on the plasmid or cloning page | No thread from colony → miniprep → Sanger → glycerol (need 5) | A construct gets N colony rows; each row carries colony PCR result, miniprep conc/260:280, Sanger verdict, and a status (picked→miniprepped→sequenced→verified→glycerol). "Promote to plasmid/glycerol stock" spawns the tube record from the winning row. | Every cloning project, ~30 clones/round | L |
| **Sequence-aware oligo entry** | Manual Tm/length for 12 oligos (need 1) | On entering a sequence: auto length, computed Tm (nearest-neighbour, note the method), GC%; warn on hairpin/dimer. | Every oligo, dozens/round | M |
| **Add primer pair** | F/R entered as 2 records with duplicated fields (need 2) | One form → two linked records sharing target/scale/box/vendor. | Every PCR | S |
| **Primer binding on the plasmid map** | Map can't show where my primers anneal (need 6) | Match Primers-DB sequences against the plasmid and draw binding sites / predict amplicon size for colony-PCR design. | Every colony-PCR design | M |
| **Sanger import + alignment** | Sanger results have nowhere to go (need 12/13) | Upload .ab1/.seq, align to the plasmid map, flag mismatches, mark the clone pass/fail. | Every construct, multiple reads | L |
| **Concentration/yield fields on plasmid tubes** | No place for Nanodrop yield/260:280 (need 12) | Structured conc + 260:280 + volume on each miniprep/glycerol record; feeds the ligation/dilution calculators. | Every miniprep | S |
| **Reusable reaction/protocol blocks (lab-shared)** | Reaction tables re-typed per page (need 3) | Lab-wide templates for digest/PCR/HiFi tables; insert with one click. | Every experiment page | S |

## 7. Bugs or confusing things
- **Primer Length/Tm never auto-compute** even though the sequence is present — feels like a
  missing feature more than a bug, but every new lab member will assume it fills in.
- **Plasmid display "#N" ≠ record id.** The row's "Delete plasmid #12" number is a per-database
  row index, while the URL is /plasmids/19. Harmless for a human, but confusing when
  cross-referencing, and it shifts as rows are added.
- **Per-person notebook Share didn't register** in my runs: selecting a colleague and clicking
  the panel's "Share" left "Not shared with anyone yet"; setting "Everyone in the lab → can
  view" worked immediately. Could be my automation, but I couldn't confirm a single-person
  share succeeded — worth a manual check.
- **"Colonies & screening" heading** in the Cloning template implies a tool that isn't there;
  it's an empty section.
- Owner field on new records is read-only (correct — only admins add for others), but the tooltip
  only appears on hover; a new user may not realise why they can't type their own name.

## 8. What worked well (honest)
- Equipment booking with **overlap refusal that names who holds it and when** — exactly right.
- The **Cloning page template**: digest/ligation/transformation with a real **ligation
  calculator** (fmol, insert:vector) and step timers, out of the box.
- **Plasmid map**: pasting GenBank/FASTA gives an interactive editable map instantly.
- **Duplicate carries the sequence**, so making a glycerol/aliquot tube from a verified
  construct is quick.
- **Orders** with grant accounts and a status board; **box grids** for tube positions.
- Real **collaboration through the app**: Rowan renamed the shared kinase experiment to match my
  construct and created their own aliquot record of pLQ02; Avery posted a KO project plan; Morgan
  set up a rotation-student guest — all visible without leaving BioManager.
- Autocomplete/suggestions across text fields keep vendor/unit spelling consistent.

## 9. Evidence
- Scripts: `testing/wetlab/quinn/scripts/` (bm.py, lib.py, s01–s37).
- Screenshots: `testing/wetlab/quinn/evidence/` — key ones: 02-plasmids,
  05-new-oligo, 08-all-oligos, 11-seq-loaded (map), 13/16/17-cloning-page,
  23-overlap-refused, 25-orders, 29-clone-tracking, 32-primer-boxgrid, 37-shared-everyone.
- Records created live on the server: 12 oligos (QA01–QA12), plasmids pLQ01/02/03 + a
  verified-clone glycerol duplicate, 3 orders to Morgan, 3 equipment bookings, 1 shared
  Cloning notebook page.
