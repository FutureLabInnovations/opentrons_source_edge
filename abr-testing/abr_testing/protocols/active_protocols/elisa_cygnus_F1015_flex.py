"""
Cygnus F1015 P. pastoris HCP ELISA - semi-automated on the Opentrons Flex.

Implements the "stamping plate" workflow recommended in Cygnus's
"Mapping and Loading your HCP ELISA Plate" best-practice guide:
  1. The single-channel pipette pre-loads a low-binding source plate with
     the full standard curve + samples in their final column layout.
  2. The 8-channel multichannel "stamps" each loaded column from the source
     plate into the assay plate in one shot, minimising positional drift.
  3. Reagent additions (HRP, TMB, Stop) are also multichannel by column.

Workflow:
  Phase A (automated):
    - Pre-load source plate with standards + samples (single-channel).
    - Step 1: stamp source plate -> assay plate (multichannel, 100 uL/well).
    - Step 2: dispense anti-HCP HRP conjugate (multichannel, 100 uL/well).
  Manual off-deck:
    - Step 3: incubation with shaking (per F1015 kit manual).
    - Step 4: 4x wash with wash buffer (Cygnus standard; volume per F1015 manual).
  Phase B (automated):
    - Step 5: dispense TMB substrate (multichannel, 100 uL/well).
    - Step 6: substrate incubation in the dark (timed delay).
    - Step 7: dispense Stop solution (multichannel, 100 uL/well).
  Manual:
    - Step 8: read absorbance at 450 nm on a plate reader.

Verified against Cygnus product literature (see sources in the PR thread):
  - Sequential sample then conjugate (NOT premixed).
  - 100 uL per well for sample, conjugate, TMB, Stop.
  - 4x wash cycle.
  - F143 standard set: 0, 1, 4, 20, 75, 250 ng/mL (6 standards; "Std 0" IS the blank).
  - Cygnus recommends duplicate as the minimum, triplicate as best practice.

Still [UNVERIFIED] (kit-specific, requires the F1015 mode d'emploi):
  - Sample/conjugate incubation time + shaking speed.
  - Substrate (TMB) incubation time -- 30 min assumed (3G convention).
  - Wash buffer volume per well -- 300 uL assumed (industry default).
  - Nunc MaxiSorp loadName -- using the lockwell-strip variant present in
    shared-data; swap for a non-lockwell custom labware if the lab uses a
    full 96-well flat MaxiSorp plate.
  - LoBind 1.5 mL tube compatibility with the SafeLock 24-tube rack.
"""

from opentrons import protocol_api

metadata = {
    "protocolName": "Cygnus F1015 P. pastoris HCP ELISA - Flex (stamping workflow)",
    "author": "Eurogentec protocol development",
    "description": (
        "Semi-automated ELISA on the Flex for the Cygnus F1015 kit. "
        "Uses Cygnus's recommended stamping-plate workflow: pre-load a "
        "source plate column-wise, then multichannel-stamp into the assay "
        "plate. Manual incubation + 4x wash between phases."
    ),
    "source": "",
}

requirements = {"robotType": "Flex", "apiLevel": "2.18"}


# -----------------------------------------------------------------------------
# Configuration (constants verified against Cygnus literature)
# -----------------------------------------------------------------------------
PER_WELL_VOLUME_UL = 100  # Sample, conjugate, TMB, Stop -- all 100 uL (Cygnus).
SOURCE_WELL_VOLUME_UL = 120  # 100 uL stamped + 20 uL dead volume in source.
NUM_STANDARDS = 6  # F143 set: 0, 1, 4, 20, 75, 250 ng/mL (the 0 standard IS the blank).
WASH_COUNT = 4  # Cygnus 3G procedure: 4x wash. [UNVERIFIED] wash volume below.
WASH_VOLUME_UL = 300  # [UNVERIFIED] - confirm in F1015 manual.

# [UNVERIFIED] - confirm in the F1015 mode d'emploi.
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
    parameters.add_int(
        variable_name="num_replicates",
        display_name="Replicates per sample/standard",
        description="Cygnus minimum is 2 (duplicate); 3 (triplicate) gives tighter CVs.",
        default=2,
        minimum=2,
        maximum=3,
    )
    parameters.add_bool(
        variable_name="dry_run",
        display_name="Dry run",
        description="Skip the substrate incubation delay for dry tests.",
        default=False,
    )


def _plan_columns(num_samples: int, num_replicates: int) -> list[list[dict]]:
    """Return one column-spec per assay-plate column. Each column-spec is a
    list of 8 dicts (rows A..H), each describing what content goes into that
    well of the source plate.

    Layout per column (8 rows):
      A..F: Std 0..Std 5 (the 6 F143 standards; Std 0 = blank).
      G:    First sample in this column pair.
      H:    Second sample in this column pair (or diluent filler if absent).

    Sample pairs map: column pair 0 -> samples 0,1; pair 1 -> samples 2,3; ...
    For each pair we emit `num_replicates` adjacent columns (the duplicate /
    triplicate of that sample pair). The standard curve is re-run in each
    column so the multichannel always stamps a full column with no waste.
    """
    sample_pair_count = max(1, (num_samples + 1) // 2)  # 1-2 samples -> 1, 3-4 -> 2
    columns: list[list[dict]] = []
    for pair_idx in range(sample_pair_count):
        for _rep in range(num_replicates):
            col: list[dict] = []
            for std_idx in range(NUM_STANDARDS):
                col.append({"kind": "standard", "index": std_idx})
            for slot in range(2):  # G, H
                sample_idx = pair_idx * 2 + slot
                if sample_idx < num_samples:
                    col.append({"kind": "sample", "index": sample_idx})
                else:
                    col.append({"kind": "diluent", "index": 0})
            columns.append(col)
    return columns


def run(protocol: protocol_api.ProtocolContext) -> None:
    num_samples: int = protocol.params.num_samples  # type: ignore[attr-defined]
    num_replicates: int = protocol.params.num_replicates  # type: ignore[attr-defined]
    dry_run: bool = protocol.params.dry_run  # type: ignore[attr-defined]

    column_plan = _plan_columns(num_samples, num_replicates)
    used_column_count = len(column_plan)

    # -------------------------------------------------------------------------
    # Trash (required on Flex)
    # -------------------------------------------------------------------------
    protocol.load_trash_bin("A3")

    # -------------------------------------------------------------------------
    # Labware
    # -------------------------------------------------------------------------
    # Assay plate: Thermo Nunc MaxiSorp (lockwell strip variant in shared-data;
    # swap for the lab's actual MaxiSorp definition if non-lockwell). [UNVERIFIED]
    assay_plate = protocol.load_labware(
        "thermofisher_nunc_maxisorp_lockwell_elisa",
        location="D1",
        label="Assay plate (Nunc MaxiSorp)",
    )

    # Source / stamping plate: low-binding 96-well flat. NEST 200 uL flat
    # is a reasonable low-binding option. The Cygnus best-practice guide
    # calls for "a low-binding, inert plate" -- any flat 96-well will work.
    source_plate = protocol.load_labware(
        "nest_96_wellplate_200ul_flat",
        location="C2",
        label="Source/stamping plate",
    )

    # Standards (6 vials) + 1-4 samples + diluent. The 24-tube rack is 4 rows
    # (A-D) x 6 cols (1-6). [UNVERIFIED] whether LoBind tubes (non-SafeLock)
    # geometrically match this rack -- treated as compatible.
    tube_rack = protocol.load_labware(
        "opentrons_24_tuberack_eppendorf_1.5ml_safelock_snapcap",
        location="D2",
        label="Standards + samples + diluent",
    )

    reservoir = protocol.load_labware(
        "nest_12_reservoir_15ml", location="C1", label="Bulk reagents"
    )

    tiprack_single = protocol.load_labware(
        "opentrons_flex_96_tiprack_200ul",
        location="B2",
        label="Flex 200 uL tips (single)",
    )
    tiprack_multi_a = protocol.load_labware(
        "opentrons_flex_96_tiprack_200ul",
        location="B3",
        label="Flex 200 uL tips (multi A)",
    )
    tiprack_multi_b = protocol.load_labware(
        "opentrons_flex_96_tiprack_200ul",
        location="A2",
        label="Flex 200 uL tips (multi B)",
    )

    # -------------------------------------------------------------------------
    # Pipettes
    # -------------------------------------------------------------------------
    p1000_single = protocol.load_instrument(
        "flex_1channel_1000",
        mount="left",
        tip_racks=[tiprack_single],
    )
    p1000_multi = protocol.load_instrument(
        "flex_8channel_1000",
        mount="right",
        tip_racks=[tiprack_multi_a, tiprack_multi_b],
    )

    # -------------------------------------------------------------------------
    # Tube + reservoir assignments
    # -------------------------------------------------------------------------
    # Tube rack layout (4 rows x 6 cols):
    #   A1..A6 -> Std 0..Std 5
    #   B1     -> Sample diluent (used for empty source wells when sample count
    #             is odd and a column has an unused row H slot)
    #   C1..C4 -> Sample 1..Sample 4
    standard_tubes = [
        tube_rack.wells_by_name()[f"A{i + 1}"] for i in range(NUM_STANDARDS)
    ]
    diluent_tube = tube_rack.wells_by_name()["B1"]
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
        name="Cygnus F143 standards (0/1/4/20/75/250 ng/mL)",
        description=(
            "Reconstituted F143 standard set for F1015. Std 0 (0 ng/mL) "
            "serves as the assay blank."
        ),
        display_color="#9b59b6",
    )
    diluent_liquid = protocol.define_liquid(
        name="Sample diluent",
        description="Used to fill unused source-plate wells so each column stamps cleanly.",
        display_color="#bdc3c7",
    )
    sample_liquid = protocol.define_liquid(
        name="Samples (pure P. pastoris supernatant)",
        description="1-4 pure samples per run.",
        display_color="#27ae60",
    )
    hrp_liquid = protocol.define_liquid(
        name="Anti-HCP:HRP conjugate",
        description="Ready-to-use anti-HCP HRP conjugate from the F1015 kit.",
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

    # How many times each tube is sampled into the source plate?
    standard_draws_per_tube = used_column_count  # standards appear in every column
    sample_draws = {idx: 0 for idx in range(num_samples)}
    diluent_draws = 0
    for col in column_plan:
        for row_idx in (NUM_STANDARDS, NUM_STANDARDS + 1):  # rows G, H
            entry = col[row_idx]
            if entry["kind"] == "sample":
                sample_draws[entry["index"]] += 1
            elif entry["kind"] == "diluent":
                diluent_draws += 1

    # Tube fill volume = draws * SOURCE_WELL_VOLUME_UL + 50 uL safety margin.
    # [UNVERIFIED] - confirm the F143 standards reconstitute volume; if it
    # falls below the required draw, reduce SOURCE_WELL_VOLUME_UL or drop
    # to duplicate-only.
    standard_fill_volume = standard_draws_per_tube * SOURCE_WELL_VOLUME_UL + 50
    for tube in standard_tubes:
        tube.load_liquid(standards_liquid, volume=standard_fill_volume)
    diluent_tube.load_liquid(
        diluent_liquid,
        volume=max(50, diluent_draws * SOURCE_WELL_VOLUME_UL + 50),
    )
    for idx, tube in enumerate(sample_tubes):
        tube.load_liquid(
            sample_liquid,
            volume=sample_draws[idx] * SOURCE_WELL_VOLUME_UL + 50,
        )

    # Reservoir reagent volumes: each used column draws 100 uL per reagent.
    reagent_volume = used_column_count * PER_WELL_VOLUME_UL + 500
    hrp_conjugate.load_liquid(hrp_liquid, volume=reagent_volume)
    tmb_substrate.load_liquid(tmb_liquid, volume=reagent_volume)
    stop_solution.load_liquid(stop_liquid, volume=reagent_volume)

    # -------------------------------------------------------------------------
    # Phase A.0 - Pre-load the source plate (single-channel, column-wise)
    # -------------------------------------------------------------------------
    # Build {tube: [source_plate_wells]} so we can pick up one tip per tube
    # and visit all of that tube's destinations before dropping the tip.
    rows = ["A", "B", "C", "D", "E", "F", "G", "H"]
    tube_to_destinations: dict[protocol_api.Well, list[protocol_api.Well]] = {}

    def add_dest(source_tube: protocol_api.Well, well_name: str) -> None:
        tube_to_destinations.setdefault(source_tube, []).append(
            source_plate.wells_by_name()[well_name]
        )

    for col_idx, col_plan in enumerate(column_plan):
        col_num = col_idx + 1
        for row_idx, entry in enumerate(col_plan):
            well_name = f"{rows[row_idx]}{col_num}"
            if entry["kind"] == "standard":
                add_dest(standard_tubes[entry["index"]], well_name)
            elif entry["kind"] == "sample":
                add_dest(sample_tubes[entry["index"]], well_name)
            else:
                add_dest(diluent_tube, well_name)

    protocol.comment("=== Phase A.0: pre-load source plate ===")
    for source_tube, destinations in tube_to_destinations.items():
        p1000_single.pick_up_tip()
        for dest in destinations:
            p1000_single.aspirate(SOURCE_WELL_VOLUME_UL, source_tube.bottom(z=2))
            p1000_single.dispense(SOURCE_WELL_VOLUME_UL, dest.bottom(z=2))
            p1000_single.blow_out(dest.top(z=-2))
        p1000_single.drop_tip()

    # -------------------------------------------------------------------------
    # Phase A.1 - Step 1: stamp source -> assay (multichannel, by column)
    # -------------------------------------------------------------------------
    protocol.comment("=== Step 1: stamp source plate -> assay plate ===")
    for col_idx in range(used_column_count):
        col_num = col_idx + 1
        src_top = source_plate.wells_by_name()[f"A{col_num}"]
        dst_top = assay_plate.wells_by_name()[f"A{col_num}"]
        p1000_multi.pick_up_tip()
        p1000_multi.aspirate(PER_WELL_VOLUME_UL, src_top.bottom(z=2))
        p1000_multi.dispense(PER_WELL_VOLUME_UL, dst_top.bottom(z=2))
        p1000_multi.blow_out(dst_top.top(z=-2))
        p1000_multi.drop_tip()

    # -------------------------------------------------------------------------
    # Phase A.2 - Step 2: dispense HRP conjugate (multichannel, by column)
    # -------------------------------------------------------------------------
    protocol.comment("=== Step 2: dispense anti-HCP:HRP conjugate ===")
    p1000_multi.pick_up_tip()
    for col_idx in range(used_column_count):
        dst_top = assay_plate.wells_by_name()[f"A{col_idx + 1}"]
        p1000_multi.aspirate(PER_WELL_VOLUME_UL, hrp_conjugate.bottom(z=2))
        p1000_multi.dispense(PER_WELL_VOLUME_UL, dst_top.bottom(z=2))
        p1000_multi.blow_out(dst_top.top(z=-2))
    p1000_multi.drop_tip()

    # -------------------------------------------------------------------------
    # Manual incubation + 4x wash
    # -------------------------------------------------------------------------
    protocol.pause(
        "Steps 3-4 (manual):\n"
        "  1. Seal the assay plate.\n"
        "  2. Incubate per the F1015 kit manual (time + shaking).\n"
        f"  3. Wash {WASH_COUNT}x with wash buffer (~{WASH_VOLUME_UL} uL/well).\n"
        "  4. Blot the plate dry, return it to slot D1, press Resume."
    )

    # -------------------------------------------------------------------------
    # Phase B - Step 5: dispense TMB substrate (multichannel, by column)
    # -------------------------------------------------------------------------
    protocol.comment("=== Step 5: dispense TMB substrate ===")
    p1000_multi.pick_up_tip()
    for col_idx in range(used_column_count):
        dst_top = assay_plate.wells_by_name()[f"A{col_idx + 1}"]
        p1000_multi.aspirate(PER_WELL_VOLUME_UL, tmb_substrate.bottom(z=2))
        p1000_multi.dispense(PER_WELL_VOLUME_UL, dst_top.bottom(z=2))
        p1000_multi.blow_out(dst_top.top(z=-2))
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
    # Phase B - Step 7: dispense Stop solution (multichannel, by column)
    # -------------------------------------------------------------------------
    protocol.comment("=== Step 7: dispense Stop solution ===")
    p1000_multi.pick_up_tip()
    for col_idx in range(used_column_count):
        dst_top = assay_plate.wells_by_name()[f"A{col_idx + 1}"]
        p1000_multi.aspirate(PER_WELL_VOLUME_UL, stop_solution.bottom(z=2))
        p1000_multi.dispense(PER_WELL_VOLUME_UL, dst_top.bottom(z=2))
        p1000_multi.blow_out(dst_top.top(z=-2))
    p1000_multi.drop_tip()

    protocol.pause(
        "Step 8 (manual): read absorbance at 450 nm on the plate reader "
        "within the time window specified in the F1015 kit manual."
    )
