"""
Cygnus F1015 P. pastoris HCP ELISA - semi-automated on the Opentrons Flex.

Flex port of abr_testing/protocols/active_protocols/elisa_cygnus_F1015_ot2.py.
Same preconditions: 1-4 pure samples per run, Nunc MaxiSorp plate, 1.5 mL
LoBind tubes, NEST 12-well reservoir, manual incubation + 4x wash between
phases.

Workflow:
  Phase A (automated):
    - Step 1: dispense standards + samples (100 uL each well) into a Nunc MaxiSorp plate.
    - Step 2: dispense anti-HCP HRP conjugate (100 uL each well) from the reservoir.
  Manual off-deck:
    - Step 3: incubation with shaking (per kit manual).
    - Step 4: 4x wash with wash buffer (~350 uL each, per kit manual).
  Phase B (automated):
    - Step 5: dispense TMB substrate (100 uL each well).
    - Step 6: substrate incubation in the dark (30 min, on-deck delay).
    - Step 7: dispense Stop solution (100 uL each well).
  Manual:
    - Step 8: read absorbance at 450 nm on a plate reader.

[UNVERIFIED] per-well volumes (100 uL chosen as Cygnus default).
[UNVERIFIED] standard curve count (6 standards + blank, duplicate).
[UNVERIFIED] substrate incubation (30 min default).
[UNVERIFIED] exact Nunc MaxiSorp loadName - using the lockwell variant present in
shared-data; swap for a non-lockwell custom definition if the lab uses a flat 96-well
MaxiSorp plate.
"""

from opentrons import protocol_api

metadata = {
    "protocolName": "Cygnus F1015 P. pastoris HCP ELISA - Flex (semi-automated)",
    "author": "Eurogentec protocol development",
    "description": (
        "Semi-automated ELISA on the Flex for the Cygnus F1015 kit. "
        "Flex handles steps 1-2 and 5-7; incubation and 4x wash are manual."
    ),
    "source": "",
}

requirements = {"robotType": "Flex", "apiLevel": "2.18"}


# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

# Volumes per well (uL). [UNVERIFIED] - confirm against the F1015 mode d'emploi.
SAMPLE_VOLUME_UL = 100
CONJUGATE_VOLUME_UL = 100
TMB_VOLUME_UL = 100
STOP_VOLUME_UL = 100

# Standard curve. [UNVERIFIED] - Cygnus F1015 commonly ships 6 standards + a zero/blank.
NUM_STANDARDS = 6
INCLUDE_BLANK = True
RUN_IN_DUPLICATE = True

# Substrate incubation, step 6. [UNVERIFIED] - confirm in kit manual.
SUBSTRATE_INCUBATION_MINUTES = 30


def add_parameters(parameters: protocol_api.Parameters) -> None:
    parameters.add_int(
        variable_name="num_samples",
        display_name="Number of samples",
        description="Number of pure samples to process (1-4 per email thread).",
        default=4,
        minimum=1,
        maximum=4,
    )
    parameters.add_bool(
        variable_name="dry_run",
        display_name="Dry run",
        description="Skip the substrate incubation delay for dry tests.",
        default=False,
    )


def run(protocol: protocol_api.ProtocolContext) -> None:
    num_samples: int = protocol.params.num_samples  # type: ignore[attr-defined]
    dry_run: bool = protocol.params.dry_run  # type: ignore[attr-defined]

    # -------------------------------------------------------------------------
    # Trash (required on Flex)
    # -------------------------------------------------------------------------
    protocol.load_trash_bin("A3")

    # -------------------------------------------------------------------------
    # Labware
    # -------------------------------------------------------------------------
    # ELISA plate: Thermo Nunc MaxiSorp. The repo only ships the "lockwell" strip
    # variant; if the lab uses a non-lockwell MaxiSorp the loadName should be
    # replaced with the appropriate custom definition. [UNVERIFIED]
    elisa_plate = protocol.load_labware(
        "thermofisher_nunc_maxisorp_lockwell_elisa", location="D1", label="ELISA plate"
    )

    # Sample / standard tubes - 1.5 mL Eppendorf. The DNA/Protein LoBind tubes
    # (Cat. 022431021 / 022431081) share the SafeLock footprint in practice;
    # the loadName below is the closest match in shared-data. [UNVERIFIED]
    tube_rack = protocol.load_labware(
        "opentrons_24_tuberack_eppendorf_1.5ml_safelock_snapcap",
        location="D2",
        label="Standards + samples",
    )

    # Bulk reagents: NEST 12-well reservoir.
    reservoir = protocol.load_labware(
        "nest_12_reservoir_15ml", location="C1", label="Reagents"
    )

    tiprack_single = protocol.load_labware(
        "opentrons_flex_96_tiprack_200ul",
        location="B2",
        label="Flex 200 uL tips (single)",
    )
    tiprack_multi = protocol.load_labware(
        "opentrons_flex_96_tiprack_200ul",
        location="B3",
        label="Flex 200 uL tips (multi)",
    )
    tiprack_spare = protocol.load_labware(
        "opentrons_flex_96_tiprack_200ul",
        location="C2",
        label="Flex 200 uL tips (spare)",
    )

    # -------------------------------------------------------------------------
    # Pipettes
    # -------------------------------------------------------------------------
    # 1-channel for sample/standard transfers from tubes; 8-channel for
    # column-wise reagent distribution.
    p1000_single = protocol.load_instrument(
        "flex_1channel_1000",
        mount="left",
        tip_racks=[tiprack_single, tiprack_spare],
    )
    p1000_multi = protocol.load_instrument(
        "flex_8channel_1000",
        mount="right",
        tip_racks=[tiprack_multi],
    )

    # -------------------------------------------------------------------------
    # Tube + reservoir assignments
    # -------------------------------------------------------------------------
    # The 24-tube rack is 4 rows (A-D) x 6 cols (1-6).
    # Layout: standards in A1..A6, blank in B1, samples in C1..C4.
    blank_tube = tube_rack.wells_by_name()["B1"] if INCLUDE_BLANK else None
    standard_tubes = [
        tube_rack.wells_by_name()[f"A{i + 1}"] for i in range(NUM_STANDARDS)
    ]
    sample_tubes = [
        tube_rack.wells_by_name()[f"C{i + 1}"] for i in range(num_samples)
    ]

    hrp_conjugate = reservoir.wells_by_name()["A1"]
    tmb_substrate = reservoir.wells_by_name()["A2"]
    stop_solution = reservoir.wells_by_name()["A3"]

    # -------------------------------------------------------------------------
    # Liquid definitions (so the Opentrons app shows liquid placement)
    # -------------------------------------------------------------------------
    standards_liquid = protocol.define_liquid(
        name="Cygnus F1015 standards",
        description="Reconstituted standards from the F1015 kit.",
        display_color="#9b59b6",
    )
    blank_liquid = protocol.define_liquid(
        name="Sample diluent / blank",
        description="Zero standard / sample diluent.",
        display_color="#bdc3c7",
    )
    sample_liquid = protocol.define_liquid(
        name="Samples (pure P. pastoris supernatant)",
        description="1-4 pure samples per run.",
        display_color="#27ae60",
    )
    hrp_liquid = protocol.define_liquid(
        name="Anti-HCP HRP conjugate",
        description="Ready-to-use conjugate from the F1015 kit.",
        display_color="#e67e22",
    )
    tmb_liquid = protocol.define_liquid(
        name="TMB substrate",
        description="Ready-to-use substrate; keep in the dark.",
        display_color="#3498db",
    )
    stop_liquid = protocol.define_liquid(
        name="Stop solution",
        description="Acidic stop solution.",
        display_color="#e74c3c",
    )

    used_columns = 2 if RUN_IN_DUPLICATE else 1
    reagent_volume_per_column = 8 * 100  # uL, multi-channel full column
    reagent_total_with_margin = used_columns * reagent_volume_per_column + 500

    hrp_conjugate.load_liquid(hrp_liquid, volume=reagent_total_with_margin)
    tmb_substrate.load_liquid(tmb_liquid, volume=reagent_total_with_margin)
    stop_solution.load_liquid(stop_liquid, volume=reagent_total_with_margin)

    for tube in standard_tubes:
        tube.load_liquid(standards_liquid, volume=200)  # [UNVERIFIED] aliquot size
    if blank_tube is not None:
        blank_tube.load_liquid(blank_liquid, volume=200)  # [UNVERIFIED]
    for tube in sample_tubes:
        tube.load_liquid(sample_liquid, volume=200)  # [UNVERIFIED]

    # -------------------------------------------------------------------------
    # Plate layout
    # -------------------------------------------------------------------------
    layout_columns: list[str] = ["1"]
    if RUN_IN_DUPLICATE:
        layout_columns.append("2")
    extra_sample_pairs = max(0, num_samples - 1)
    for i in range(extra_sample_pairs):
        layout_columns.append(str(3 + 2 * i))
        if RUN_IN_DUPLICATE:
            layout_columns.append(str(4 + 2 * i))

    def plate_well(column: str, row_letter: str) -> protocol_api.Well:
        return elisa_plate.wells_by_name()[f"{row_letter}{column}"]

    standards_and_samples: list[tuple[protocol_api.Well, list[protocol_api.Well]]] = []

    base_pair = [layout_columns[0]]
    if RUN_IN_DUPLICATE:
        base_pair.append(layout_columns[1])

    if blank_tube is not None:
        standards_and_samples.append(
            (blank_tube, [plate_well(col, "A") for col in base_pair])
        )

    for idx, std_tube in enumerate(standard_tubes):
        row_letter = chr(ord("B") + idx)  # B, C, D, E, F, G
        standards_and_samples.append(
            (std_tube, [plate_well(col, row_letter) for col in base_pair])
        )

    for idx, sample_tube in enumerate(sample_tubes):
        if idx == 0:
            cols_for_sample = base_pair
        else:
            start = 2 + (idx - 1) * (2 if RUN_IN_DUPLICATE else 1)
            cols_for_sample = layout_columns[
                start : start + (2 if RUN_IN_DUPLICATE else 1)
            ]
        standards_and_samples.append(
            (sample_tube, [plate_well(col, "H") for col in cols_for_sample])
        )

    # -------------------------------------------------------------------------
    # Phase A - Step 1: dispense standards, blank, and samples
    # -------------------------------------------------------------------------
    protocol.comment("=== Step 1: dispense standards, blank, and samples ===")
    for source_tube, destinations in standards_and_samples:
        p1000_single.pick_up_tip()
        for dest in destinations:
            p1000_single.aspirate(SAMPLE_VOLUME_UL, source_tube.bottom(z=2))
            p1000_single.dispense(SAMPLE_VOLUME_UL, dest.bottom(z=2))
            p1000_single.blow_out(dest.top(z=-2))
        p1000_single.drop_tip()

    # -------------------------------------------------------------------------
    # Phase A - Step 2: dispense HRP conjugate to all used columns
    # -------------------------------------------------------------------------
    protocol.comment("=== Step 2: dispense anti-HCP HRP conjugate ===")
    p1000_multi.pick_up_tip()
    for col in layout_columns:
        top_well = plate_well(col, "A")
        p1000_multi.aspirate(CONJUGATE_VOLUME_UL, hrp_conjugate.bottom(z=2))
        p1000_multi.dispense(CONJUGATE_VOLUME_UL, top_well.bottom(z=2))
        p1000_multi.blow_out(top_well.top(z=-2))
    p1000_multi.drop_tip()

    # -------------------------------------------------------------------------
    # Manual incubation + 4x wash
    # -------------------------------------------------------------------------
    protocol.pause(
        "Steps 3-4 (manual):\n"
        "  1. Seal the ELISA plate.\n"
        "  2. Incubate per the F1015 kit manual (time + shaking per mode d'emploi).\n"
        "  3. Wash 4x with wash buffer (~350 uL per well per wash).\n"
        "  4. Blot the plate dry, return it to slot D1, and press Resume."
    )

    # -------------------------------------------------------------------------
    # Phase B - Step 5: dispense TMB substrate
    # -------------------------------------------------------------------------
    protocol.comment("=== Step 5: dispense TMB substrate ===")
    p1000_multi.pick_up_tip()
    for col in layout_columns:
        top_well = plate_well(col, "A")
        p1000_multi.aspirate(TMB_VOLUME_UL, tmb_substrate.bottom(z=2))
        p1000_multi.dispense(TMB_VOLUME_UL, top_well.bottom(z=2))
        p1000_multi.blow_out(top_well.top(z=-2))
    p1000_multi.drop_tip()

    # -------------------------------------------------------------------------
    # Phase B - Step 6: substrate incubation
    # -------------------------------------------------------------------------
    if dry_run:
        protocol.comment("Dry run - skipping substrate incubation delay.")
    else:
        protocol.delay(
            minutes=SUBSTRATE_INCUBATION_MINUTES,
            msg=(
                f"Step 6: substrate incubation in the dark "
                f"({SUBSTRATE_INCUBATION_MINUTES} min)."
            ),
        )

    # -------------------------------------------------------------------------
    # Phase B - Step 7: dispense stop solution
    # -------------------------------------------------------------------------
    protocol.comment("=== Step 7: dispense Stop solution ===")
    p1000_multi.pick_up_tip()
    for col in layout_columns:
        top_well = plate_well(col, "A")
        p1000_multi.aspirate(STOP_VOLUME_UL, stop_solution.bottom(z=2))
        p1000_multi.dispense(STOP_VOLUME_UL, top_well.bottom(z=2))
        p1000_multi.blow_out(top_well.top(z=-2))
    p1000_multi.drop_tip()

    protocol.pause(
        "Step 8 (manual): read absorbance at 450 nm on the plate reader "
        "within the time window specified in the F1015 kit manual."
    )
