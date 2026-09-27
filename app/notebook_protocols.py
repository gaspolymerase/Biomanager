"""Common bench protocols that come with the notebook.

Each is an ordinary protocol page in Markdown: Materials, numbered Steps
(which become a checklist when inserted into a page or when an experiment
is started from it) and Notes. A lab inserts one into a page as it is, or
saves a copy as its own protocol page to change and number.

They are starting points written for a typical lab. Every lab should check
amounts, times and animal procedures against its own approved protocols
before relying on them.
"""
from __future__ import annotations

PRESET_PROTOCOLS: dict[str, dict] = {
    "hotshot": {
        "title": "Mouse genotyping: HotSHOT DNA extraction",
        "category": "Genotyping",
        "summary": "Tail or ear DNA ready for PCR in 45 minutes.",
        "body": """## Materials
- Tail tip (2 mm) or ear punch, in a PCR strip tube
- Alkaline lysis reagent: 25 mM NaOH, 0.2 mM EDTA (pH ~12)
- Neutralisation buffer: 40 mM Tris-HCl, pH 5.0
- Thermocycler or heat block

## Steps
1. Add 75 µL alkaline lysis reagent to each sample; make sure the tissue is covered.
2. Heat at 95 °C for 30 min.
3. Cool to 4 °C (on ice or hold in the cycler).
4. Add 75 µL neutralisation buffer and mix by pipetting.
5. Spin 1 min to pellet debris.
6. Use 1–2 µL of the supernatant per 20 µL PCR. Store at 4 °C (weeks) or −20 °C.

## Notes
- Include a no-tissue blank and a known positive in every run.
- Clean punches with 70% ethanol between animals to avoid carry-over.
""",
    },
    "genotyping-pcr": {
        "title": "Genotyping PCR and agarose gel",
        "category": "Genotyping",
        "summary": "Standard 20 µL PCR and a 2% gel to read the bands.",
        "body": """## Materials
- 2× PCR master mix (Taq, dNTPs, MgCl₂, loading dye)
- Primers, 10 µM each
- DNA (HotSHOT supernatant)
- Agarose, 1× TAE, DNA stain, 100 bp ladder

## Steps
1. Make a master mix per reaction: 10 µL 2× mix, 0.5 µL each primer, water to 18 µL (plus 10% extra reactions).
2. Add 18 µL to each tube, then 2 µL DNA. Include wild-type, heterozygous, homozygous and no-template controls.
3. Cycle: 94 °C 3 min; 35 × (94 °C 30 s, 60 °C 30 s, 72 °C 45 s); 72 °C 5 min; hold 4 °C.
4. Cast a 2% agarose gel in 1× TAE with DNA stain.
5. Load 10 µL per lane and the ladder at each end.
6. Run at 120 V for 30–40 min, until the dye front is two-thirds down.
7. Image the gel, record each animal's genotype, and paste the gel picture here.

## Notes
- Annealing temperature and extension time depend on the primers and product size.
""",
    },
    "perfusion": {
        "title": "Transcardial perfusion with PFA",
        "category": "Tissue",
        "summary": "Fix the brain (or other organs) for sectioning.",
        "body": """## Materials
- Anaesthetic per your approved animal protocol
- Ice-cold PBS (≈20 mL per mouse) and ice-cold 4% PFA in PBS (≈20 mL per mouse)
- Perfusion pump or gravity line, 25–27 G needle, surgical tools
- Fume hood; 4% PFA and 30% sucrose in PBS for post-fixation

## Steps
1. Deeply anaesthetise the mouse; confirm there is no toe-pinch reflex.
2. Open the abdomen and cut the diaphragm and rib cage to expose the heart.
3. Insert the needle into the left ventricle and cut the right atrium.
4. Perfuse ice-cold PBS (about 5 mL/min) until the liver clears and the fluid runs clear.
5. Switch to ice-cold 4% PFA and perfuse the same volume; look for fixation tremors and stiffening.
6. Dissect the brain (or organs) and post-fix in 4% PFA overnight at 4 °C.
7. Move to 30% sucrose at 4 °C until the tissue sinks (1–2 days), then freeze or section.

## Notes
- Follow your institution's approved protocol for anaesthesia and euthanasia.
- Work with PFA in a fume hood; collect waste as hazardous.
""",
    },
    "if-free-floating": {
        "title": "Immunofluorescence on free-floating brain sections",
        "category": "Tissue",
        "summary": "Staining 30–40 µm sections in well plates.",
        "body": """## Materials
- Sections in PBS (24- or 12-well plate, netwells if you have them)
- PBS, PBST (PBS + 0.3% Triton X-100)
- Blocking buffer: 5% normal donkey serum in PBST
- Primary and fluorescent secondary antibodies; DAPI
- Slides, mounting medium, coverslips

## Steps
1. Wash sections 3 × 10 min in PBS.
2. Block 1 h at room temperature in blocking buffer.
3. Incubate in primary antibody in blocking buffer overnight at 4 °C, gently shaking.
4. Wash 3 × 10 min in PBST.
5. Incubate in secondary antibody (1:500–1:1000) in blocking buffer 2 h at room temperature, protected from light.
6. Wash 3 × 10 min in PBS; add DAPI (1:5000) in the second wash.
7. Mount on slides, let dry briefly, and coverslip with mounting medium.
8. Image within a week; store slides at 4 °C in the dark.

## Notes
- Record antibodies, dilutions and lots in a Materials table (type /materials).
""",
    },
    "western": {
        "title": "Western blot",
        "category": "Protein",
        "summary": "SDS-PAGE, transfer and immunodetection.",
        "body": """## Materials
- Lysates quantified by BCA; 4× Laemmli buffer with reducing agent
- Precast or hand-cast SDS-PAGE gel, running buffer, protein ladder
- PVDF or nitrocellulose membrane, transfer buffer
- TBST (TBS + 0.1% Tween-20), 5% milk or BSA in TBST
- Primary and HRP secondary antibodies, ECL substrate

## Steps
1. Mix 20–30 µg protein with Laemmli buffer; heat at 95 °C for 5 min (70 °C 10 min for membrane proteins).
2. Load samples and ladder; run at 120 V until the dye front reaches the bottom.
3. Transfer to membrane (wet: 100 V 1 h cold, or your semi-dry settings).
4. Check transfer with Ponceau S, image it, rinse off.
5. Block 1 h in 5% milk (or BSA for phospho-antibodies) in TBST.
6. Incubate primary antibody overnight at 4 °C.
7. Wash 3 × 10 min in TBST.
8. Incubate HRP secondary 1 h at room temperature.
9. Wash 3 × 10 min in TBST.
10. Develop with ECL and image; re-probe for a loading control.

## Notes
- Methanol-activate PVDF before transfer; never let it dry.
""",
    },
    "bca": {
        "title": "BCA protein assay (microplate)",
        "category": "Protein",
        "summary": "Protein concentration from a BSA standard curve.",
        "body": """## Materials
- BCA reagents A and B, BSA standard (2 mg/mL)
- 96-well plate, plate reader at 562 nm

## Steps
1. Prepare BSA standards: 0, 25, 125, 250, 500, 750, 1000, 1500, 2000 µg/mL, in the same buffer as the samples.
2. Dilute samples so they fall inside the standard range (try 1:5 and 1:10).
3. Pipette 10 µL of each standard and sample in duplicate.
4. Mix working reagent (A:B = 50:1) and add 200 µL per well.
5. Cover and incubate 30 min at 37 °C.
6. Cool to room temperature and read absorbance at 562 nm.
7. Fit the standard curve and calculate concentrations (type /plate for a plate-reader block).

## Notes
- Reducing agents and chelators interfere; check the kit's compatibility table.
""",
    },
    "transformation": {
        "title": "Bacterial transformation (heat shock)",
        "category": "Molecular cloning",
        "summary": "Chemically competent E. coli, e.g. DH5α or Stbl3.",
        "body": """## Materials
- Chemically competent E. coli (50 µL aliquot), thawed on ice
- Plasmid DNA (1–100 ng) or ligation
- SOC medium, LB plates with the right antibiotic, 42 °C water bath

## Steps
1. Thaw competent cells on ice for 10 min.
2. Add 1–5 µL DNA, flick gently to mix; do not pipette up and down.
3. Incubate on ice for 30 min.
4. Heat shock at 42 °C for 45 s.
5. Return to ice for 2 min.
6. Add 250 µL SOC and shake at 37 °C for 1 h (30 °C for lentiviral plasmids in Stbl3).
7. Spread 50–200 µL on a pre-warmed selective plate.
8. Incubate overnight at 37 °C (or 30 °C); pick colonies the next day.

## Notes
- Ampicillin plates can skip the 1 h recovery; kanamycin and others need it.
""",
    },
    "miniprep": {
        "title": "Plasmid miniprep (spin column)",
        "category": "Molecular cloning",
        "summary": "High-copy plasmid from a 5 mL overnight culture.",
        "body": """## Materials
- 3–5 mL overnight LB culture with antibiotic
- Miniprep kit: resuspension (with RNase A), lysis, neutralisation, wash buffers, spin columns
- Elution buffer or water

## Steps
1. Pellet the culture at 6,000 × g for 3 min; remove all medium.
2. Resuspend the pellet completely in 250 µL resuspension buffer.
3. Add 250 µL lysis buffer and invert 6 times; do not vortex; do not exceed 5 min.
4. Add 350 µL neutralisation buffer and invert immediately until the mix is uniform.
5. Spin at top speed for 10 min.
6. Load the supernatant onto the column; spin 1 min; discard flow-through.
7. Wash with the kit's wash buffer; spin 1 min; discard.
8. Spin the empty column 1 min to dry it.
9. Elute in 30–50 µL buffer, wait 1 min, spin 1 min.
10. Measure concentration and A260/280; label the tube and add the plasmid to the Plasmids database.
""",
    },
    "trizol-rna": {
        "title": "RNA extraction with TRIzol",
        "category": "RNA and qPCR",
        "summary": "Total RNA from tissue or cells.",
        "body": """## Materials
- TRIzol (in a fume hood), chloroform, isopropanol, 75% ethanol in RNase-free water
- RNase-free tubes and tips; homogeniser for tissue
- RNase-free water

## Steps
1. Homogenise tissue (≤100 mg) or lyse cells in 1 mL TRIzol; incubate 5 min at room temperature.
2. Add 200 µL chloroform, shake 15 s, and stand 3 min.
3. Spin at 12,000 × g for 15 min at 4 °C.
4. Move the clear upper phase to a new tube without touching the interphase.
5. Add 500 µL isopropanol, mix, and stand 10 min; spin 12,000 × g for 10 min at 4 °C.
6. Remove the supernatant; wash the pellet with 1 mL 75% ethanol; spin 7,500 × g for 5 min.
7. Air-dry the pellet for 5–10 min (do not over-dry).
8. Dissolve in 20–50 µL RNase-free water; measure concentration, A260/280 and A260/230.
9. Store at −80 °C.

## Notes
- TRIzol contains phenol: gloves, goggles and fume hood; collect waste separately.
""",
    },
    "qpcr": {
        "title": "cDNA synthesis and qPCR setup",
        "category": "RNA and qPCR",
        "summary": "Reverse transcription, then SYBR qPCR in triplicate.",
        "body": """## Materials
- RNA (equal amounts per sample, e.g. 500 ng), DNase if needed
- Reverse transcription kit
- 2× SYBR Green master mix, primers (10 µM), 96- or 384-well qPCR plate

## Steps
1. Treat RNA with DNase if the primers do not span an exon junction.
2. Set up reverse transcription with the same RNA amount for every sample; include a no-RT control.
3. Run the RT programme; dilute cDNA 1:5–1:10 in water.
4. Per 10 µL reaction: 5 µL SYBR mix, 0.4 µL each primer, 2 µL cDNA, water to 10 µL.
5. Plate every sample in triplicate for the target and a reference gene; include no-template controls.
6. Seal, spin the plate briefly, and run: 95 °C 2 min; 40 × (95 °C 15 s, 60 °C 1 min); melt curve.
7. Check melt curves for a single peak, then paste Ct values into a qPCR block (type /qpcr) for ΔΔCt.
""",
    },
    "cell-passage": {
        "title": "Passaging adherent cells",
        "category": "Cell culture",
        "summary": "Split a confluent flask with trypsin.",
        "body": """## Materials
- Complete medium, PBS without Ca²⁺/Mg²⁺, 0.05% trypsin-EDTA (all at 37 °C)
- Biosafety cabinet, new flasks or plates

## Steps
1. Check the cells under the microscope: 80–90% confluent, healthy, no contamination.
2. Aspirate the medium and rinse once with PBS.
3. Add trypsin to cover the cells (1 mL per T25, 3 mL per T75); incubate 2–5 min at 37 °C.
4. Tap the flask to detach the cells; check under the microscope.
5. Add at least twice the trypsin volume of complete medium to stop it; pipette to break clumps.
6. Count the cells if you need an exact density.
7. Seed new flasks at the split ratio or density you use (for example 1:5–1:10).
8. Label flasks with cell line, passage number, date and your initials; return to the incubator.

## Notes
- Record the passage number each time; retire lines above your lab's limit.
""",
    },
    "tamoxifen": {
        "title": "Tamoxifen preparation and i.p. injection",
        "category": "Animals",
        "summary": "Inducing CreER lines: 20 mg/mL in corn oil.",
        "body": """## Materials
- Tamoxifen powder (light-sensitive), corn oil
- Glass vial wrapped in foil, 37 °C shaker or rotator
- 1 mL syringes, 25–27 G needles; scale

## Steps
1. Weigh tamoxifen and add corn oil for 20 mg/mL (e.g. 100 mg in 5 mL).
2. Dissolve by shaking at 37 °C, protected from light, until clear (overnight is common).
3. Store at 4 °C in the dark for up to a month, or aliquot and freeze.
4. Warm to 37 °C before use and mix.
5. Weigh each mouse and calculate its dose (commonly 75–100 mg/kg, i.e. 3.75–5 µL/g at 20 mg/mL).
6. Inject intraperitoneally, once a day for the number of days your line needs (often 5).
7. Record each injection (date, mouse, dose) and monitor the mice for weight loss.

## Notes
- Follow the dose and schedule in your approved animal protocol and for your line.
- Tamoxifen is hazardous: wear gloves, handle powder in a hood, and label cages.
""",
    },
}


def preset_list() -> list[dict]:
    """The built-in protocols without their text, for a library list."""
    return [{"key": key, "title": p["title"], "category": p["category"], "summary": p["summary"]}
            for key, p in PRESET_PROTOCOLS.items()]
