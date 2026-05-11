"""
OT-2 Trade Fair Demo  -  "A Day in the Lab" in Color (NEST flat-bottom)
=======================================================================

Autonomous, eye-catching demo for trade-fair audiences. Each of six plates
showcases a real, recognizable laboratory technique using food-coloring as
the "sample". Total runtime ~2 hours.

This is the NEST flat-bottom 200 uL variant of the demo, built around the
labware actually on hand at the booth. Twin of demos/trade_fair_color_matrix.py
(which targets Thermo Fisher Armadillo 200 uL PCR plates instead). No
Falcon 15/50 mL tube adapter is required - all reagent storage stays on
the 12-channel NEST reservoir.

The workflows cycle through three classic techniques that any wet-lab
visitor will recognize, executed back-to-back:

  1. Serial Dilution / Standard Curve preparation
       The bread-and-butter of any quantitative assay. A 1:2 serial dilution
       is performed across columns 1 -> 11, with column 12 left as the
       no-sample blank. Rows are loaded with four different "samples"
       (red, yellow, blue, and a red+blue mix) so each plate shows four
       horizontal color gradients.

  2. Combinatorial Dose-Response Matrix (drug-synergy checkerboard)
       Two "compounds" (red across columns, blue down rows) are titrated
       against each other to fill the plate with 96 unique combinations -
       the same layout used for Bliss / Loewe synergy studies. A yellow
       indicator pass at the end mimics adding a viability dye.

  3. Multiplex Plate Map (assay layout)
       Different reagents are distributed into defined column blocks, the
       way a multiplex assay or compound library is mapped onto a plate.
       Single-channel "controls" are spotted into specific wells.

Pipettes (no modules used):
  - left  : P300 Single-Channel GEN2  -> sample loading, controls, indicators
  - right : P300 Multi-Channel  GEN2  -> bulk fills, serial dilution transfers

Tip strategy (real lab practice):
  - Single-channel rack is sectioned by reagent so a tip never sees more
    than one color (no cross-contamination):
        cols 1-3  -> red tips
        cols 4-6  -> yellow tips
        cols 7-9  -> blue tips
        cols 10-12-> wash/water tips
  - Multi-channel uses fresh tip columns for the first WASH_TRIGGER_PLATE
    plates, then switches to wash-and-reuse mode (3x rinse in the bulk
    water reservoir between colors, returned to the rack for re-use).

Runtime parameters (set in the Opentrons app before starting the run):
  * Per-plate viewing delay (s) - pause after each finished plate so
    visitors can admire the result. Lever for hitting >= 2 hr runtime.
  * Incubation delay per plate (s) - mimics a real assay incubation
    between plates (set 0 to skip).

Materials needed
----------------
Hardware (already on robot):
  * Opentrons OT-2
  * P300 Multi-Channel GEN2  (right mount)
  * P300 Single-Channel GEN2 (left mount)

Labware:
  * 6 x nest_96_wellplate_200ul_flat      (NEST 96-well 200 uL Flat-bottom,
        slots 2, 5, 6, 7, 8, 11 - clear flat-bottom is ideal for color
        visibility under a white light pad)
  * 1 x nest_12_reservoir_15ml            (slot 4: dye stocks + diluent)
  * 1 x nest_1_reservoir_195ml            (slot 9: bulk water for tip wash)
  * 3 x opentrons_96_tiprack_300ul        (slots 1, 3, 10)

No tube adapter for 15/50 mL Falcons is needed; the only off-deck consumables
are the food-coloring stocks (poured directly into the 12-channel reservoir
lanes) and the wash water (poured into the 1-well reservoir).

Reagents (food-grade, non-hazardous):
  * Red, yellow, and blue food coloring (~10 mL each, diluted 1:5 in water
    in their reservoir lanes for vivid but not over-saturated color)
  * Distilled water - ~180 mL in the bulk 195 mL reservoir. This reservoir
    serves as BOTH the diluent source and the tip-wash station; the wash
    step mixes in place without consuming water, so a single fill lasts
    the full 2-hour run.

Reservoir layout (NEST 12-channel, slot 4):
   A1=red  A2=yellow  A3=blue  A4..A12=spare (unused; available for additional
                                              dyes if you extend the protocol)

Setup tip:
  Place a white sheet or LED light pad under the OT-2 deck. The NEST plate's
  clear flat-bottom wells light up beautifully and the gradients read clearly
  from across the room.
"""

from opentrons import protocol_api

metadata = {
    "protocolName": "Trade Fair - A Day in the Lab (NEST flat-bottom)",
    "author": "Opentrons Demo",
    "description": (
        "Autonomous ~2-hour OT-2 demo using P300 multi + P300 single. "
        "Cycles through serial dilution, dose-response matrix, and "
        "multiplex plate-layout workflows on NEST 96-well 200 uL "
        "flat-bottom plates. No Falcon tube adapter required."
    ),
}

# 2.18+ is required for runtime parameters (add_parameters / protocol.params).
requirements = {"robotType": "OT-2", "apiLevel": "2.18"}


# ---------------------------------------------------------------------------
# Tunables
# ---------------------------------------------------------------------------

# Reservoir lane assignments (NEST 12-well, slot 4)
RED, YELLOW, BLUE, DILUENT = "A1", "A2", "A3", "A4"

# Single-channel tip-rack sections (1-indexed column ranges, inclusive).
# Each reagent only ever uses tips from its own section.
TIP_SECTIONS = {
    "red":    (1, 3),
    "yellow": (4, 6),
    "blue":   (7, 9),
    "wash":   (10, 12),
}

# After this plate index (0-based), multi-channel switches to wash-and-reuse.
WASH_TRIGGER_PLATE = 2

# P300 lower limit; any computed volume below this is skipped.
MIN_DISPENSE_UL = 20

# Plate geometry (NEST 96 Well Plate, 200 uL Flat-bottom).
PLATE_LOAD_NAME = "nest_96_wellplate_200ul_flat"
N_ROWS, N_COLS  = 8, 12
WELL_MAX_UL     = 200
WORK_VOL_UL     = 100   # standard per-well working volume


# ---------------------------------------------------------------------------
# Runtime parameters
# ---------------------------------------------------------------------------

def add_parameters(parameters):
    parameters.add_int(
        variable_name="viewing_delay_s",
        display_name="Per-plate viewing delay",
        description="Pause after each finished plate. Increase to extend the demo runtime.",
        default=60,
        minimum=0,
        maximum=600,
        unit="s",
    )
    parameters.add_int(
        variable_name="incubation_delay_s",
        display_name="Per-plate incubation delay",
        description="Per-plate pause that mimics an assay incubation (e.g. standard-curve settling).",
        default=120,
        minimum=0,
        maximum=900,
        unit="s",
    )


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------

def run(protocol: protocol_api.ProtocolContext):

    viewing_delay_s    = protocol.params.viewing_delay_s
    incubation_delay_s = protocol.params.incubation_delay_s

    # Labware ---------------------------------------------------------------
    reservoir    = protocol.load_labware("nest_12_reservoir_15ml",   4)
    wash_station = protocol.load_labware("nest_1_reservoir_195ml",   9)

    plates = [
        protocol.load_labware(PLATE_LOAD_NAME, slot, f"plate {i + 1}")
        for i, slot in enumerate([2, 5, 6, 7, 8, 11])
    ]

    rack_single  = protocol.load_labware("opentrons_96_tiprack_300ul", 1, "single tips")
    rack_multi_a = protocol.load_labware("opentrons_96_tiprack_300ul", 3, "multi tips A")
    rack_multi_b = protocol.load_labware("opentrons_96_tiprack_300ul", 10, "multi tips B")

    # Pipettes --------------------------------------------------------------
    p300s = protocol.load_instrument("p300_single_gen2", "left",
                                     tip_racks=[rack_single])
    p300m = protocol.load_instrument("p300_multi_gen2",  "right",
                                     tip_racks=[rack_multi_a, rack_multi_b])

    p300s.flow_rate.aspirate = 100
    p300s.flow_rate.dispense = 200
    p300m.flow_rate.aspirate = 100
    p300m.flow_rate.dispense = 200

    # Sectioned tip pools for the single-channel pipette --------------------
    def section_wells(start_col, end_col):
        return [f"{row}{col}"
                for col in range(start_col, end_col + 1)
                for row in "ABCDEFGH"]

    tip_pools = {color: section_wells(s, e) for color, (s, e) in TIP_SECTIONS.items()}
    tip_index = {color: 0 for color in tip_pools}

    def pick_single_tip(color: str) -> None:
        if tip_index[color] >= len(tip_pools[color]):
            raise RuntimeError(
                f"Out of {color} tips - section exhausted "
                f"({tip_index[color]}/{len(tip_pools[color])})."
            )
        well_name = tip_pools[color][tip_index[color]]
        tip_index[color] += 1
        p300s.pick_up_tip(rack_single.wells_by_name()[well_name])

    # Multi-channel tip management -----------------------------------------
    multi_columns = []
    for rack in (rack_multi_a, rack_multi_b):
        for col in range(12):
            multi_columns.append(rack.columns()[col][0])
    multi_idx = {"next": 0}

    def multi_pick_fresh():
        if multi_idx["next"] >= len(multi_columns):
            raise RuntimeError("Out of multi-channel tip columns.")
        target = multi_columns[multi_idx["next"]]
        multi_idx["next"] += 1
        p300m.pick_up_tip(target)

    def multi_wash_in_reservoir():
        # Real-lab tip-wash pattern: 4 mix cycles in the bulk water reservoir,
        # then a blow-out at the surface to clear residual dye. (Same pattern
        # the proven internal serial-dilution protocol uses.)
        p300m.mix(4, 250, wash_station["A1"].bottom(2))
        p300m.blow_out(wash_station["A1"].top(-3))

    def single_wash_in_reservoir():
        # Same wash pattern, scaled to a single-channel volume.
        p300s.mix(4, 200, wash_station["A1"].bottom(2))
        p300s.blow_out(wash_station["A1"].top(-3))

    def finish_multi(wash_mode: bool):
        if wash_mode:
            multi_wash_in_reservoir()
            p300m.return_tip()
        else:
            p300m.drop_tip()

    # Reservoir-source mapping and volume tracking --------------------------
    # The 3 dyes live in NEST 12-channel troughs (~14 mL usable each). The
    # diluent comes from the bulk 195 mL reservoir on slot 9, which also
    # doubles as the tip-wash station - the wash step does mix() with the
    # same tip in the same trough, so no net water is consumed by washing.
    # Tracking per source lets us abort cleanly rather than aspirate air
    # after many transfers, the same idea as the proven protocol's
    # TubeTracker, minus the cone math (these are flat troughs).
    sources = {
        RED:     reservoir[RED],
        YELLOW:  reservoir[YELLOW],
        BLUE:    reservoir[BLUE],
        DILUENT: wash_station["A1"],
    }
    caps_ul = {
        RED:     14_000,
        YELLOW:  14_000,
        BLUE:    14_000,
        DILUENT: 180_000,   # 180 mL of the 195 mL bulk reservoir
    }
    lane_used_ul = {RED: 0, YELLOW: 0, BLUE: 0, DILUENT: 0}

    def aspirate_tracked(pipette, vol_ul: int, lane: str, channels: int = 1):
        # channels=8 for multi-channel (each of 8 channels takes vol_ul, all
        # from the same trough since a NEST lane and the bulk reservoir are
        # both wide enough to accept all 8 channels side by side).
        draw_ul = vol_ul * channels
        if lane_used_ul[lane] + draw_ul > caps_ul[lane]:
            raise RuntimeError(
                f"Reservoir source {lane} would be exhausted "
                f"(used {lane_used_ul[lane]} uL, attempting {draw_ul} uL more, "
                f"cap {caps_ul[lane]} uL)."
            )
        lane_used_ul[lane] += draw_ul
        pipette.aspirate(vol_ul, sources[lane])

    def dispense_and_lift(pipette, vol_ul: int, well, lift_z: int = -2):
        # Proven touch-off-without-touch-tip pattern: dispense above the
        # liquid line (well.top(z=-5)), then hover at top(z=lift_z) to let
        # any hanging droplet drop into the well rather than be dragged to
        # the next location.
        pipette.dispense(vol_ul, well.top(z=-5))
        pipette.move_to(well.top(z=lift_z))

    # ----------------------------------------------------------------------
    # Workflow 1: Serial Dilution / Standard Curve
    # ----------------------------------------------------------------------
    # Volume math taken from the lab's proven internal protocol:
    #   * 75 uL diluent pre-loaded into columns 2..12 (the "dilution wells").
    #   * 150 uL of stock sample loaded into column 1, four samples in row
    #     pairs: red (A,B), yellow (C,D), blue (E,F), and a R+B / R+Y mix
    #     (G,H) depending on the variant.
    #   * Multi-channel performs a 1:2 serial dilution across columns 1->11
    #     with 75 uL transfers + mix at each step. Column 12 stays as the
    #     no-sample blank - real labs always leave a blank for QC.
    #   * Per-well end volume ~75-150 uL, well within the NEST 200 uL plate.
    def workflow_serial_dilution(plate, plate_idx: int, variant: str):
        wash_mode  = plate_idx >= WASH_TRIGGER_PLATE
        diluent_ul = 75
        stock_ul   = 150
        xfer_ul    = 75
        mix_ul     = 75
        mix_reps   = 4

        protocol.comment(
            f"=== Plate {plate_idx + 1} | SERIAL DILUTION ({variant}) ==="
        )

        # 1) Multi-channel: pre-load diluent into columns 2..12, dispensing
        #    from above and lifting off the surface to break droplets.
        multi_pick_fresh()
        for col in range(1, N_COLS):
            aspirate_tracked(p300m, diluent_ul, DILUENT, channels=8)
            dispense_and_lift(p300m, diluent_ul, plate.columns()[col][0])
        finish_multi(wash_mode)

        # 2) Single-channel: load 4 different stock samples into column 1.
        #    Pair-of-rows layout produces two identical horizontal gradients
        #    per sample (real labs run technical replicates this way).
        if variant == "RYB+purple":
            sample_layout = [
                ("red",    ["A1", "B1"], stock_ul,  None),
                ("yellow", ["C1", "D1"], stock_ul,  None),
                ("blue",   ["E1", "F1"], stock_ul,  None),
                ("red",    ["G1", "H1"], stock_ul // 2, "blue_addition"),
            ]
        else:  # "RYB+orange": orange = red + yellow
            sample_layout = [
                ("red",    ["A1", "B1"], stock_ul,  None),
                ("blue",   ["C1", "D1"], stock_ul,  None),
                ("yellow", ["E1", "F1"], stock_ul,  None),
                ("red",    ["G1", "H1"], stock_ul // 2, "yellow_addition"),
            ]

        color_to_lane = {"red": RED, "yellow": YELLOW, "blue": BLUE}
        for color, wells, vol, follow_up in sample_layout:
            pick_single_tip(color)
            for w in wells:
                aspirate_tracked(p300s, vol, color_to_lane[color])
                dispense_and_lift(p300s, vol, plate.wells_by_name()[w])
            p300s.drop_tip()
            if follow_up in ("blue_addition", "yellow_addition"):
                mix_color = "blue" if follow_up == "blue_addition" else "yellow"
                mix_lane  = BLUE   if mix_color == "blue"           else YELLOW
                pick_single_tip(mix_color)
                for w in wells:
                    target = plate.wells_by_name()[w]
                    aspirate_tracked(p300s, stock_ul // 2, mix_lane)
                    p300s.dispense(stock_ul // 2, target.bottom(2))
                    p300s.mix(2, mix_ul, target.bottom(2))
                    p300s.move_to(target.top(z=-2))
                p300s.drop_tip()

        # 3) Multi-channel: 1:2 serial dilution across columns 1 -> 11.
        #    Same column-by-column transfer + mix pattern as the lab's
        #    proven protocol. Dilution tips see every color in succession
        #    so they cannot be re-used - drop them at the end.
        multi_pick_fresh()
        for col in range(N_COLS - 2):  # transfers col 0..10 -> col 1..11
            src = plate.columns()[col][0].bottom(2)
            dst = plate.columns()[col + 1][0].bottom(2)
            p300m.aspirate(xfer_ul, src)
            p300m.dispense(xfer_ul, dst)
            p300m.mix(mix_reps, mix_ul, dst)
            p300m.blow_out(plate.columns()[col + 1][0].top(z=-2))
        p300m.drop_tip()

    # ----------------------------------------------------------------------
    # Workflow 2: Combinatorial Dose-Response Matrix
    # ----------------------------------------------------------------------
    # Real lab practice:
    #   * Compound A (red) titrated across columns 1->12 in a decreasing
    #     concentration gradient. All 8 rows get the same volume per column.
    #   * Compound B (blue) titrated down rows A->H in an increasing
    #     gradient. Done with the single-channel because per-row volume
    #     varies.
    #   * A constant yellow "viability indicator" goes into the central
    #     wells (the experimental region) - a real lab would add resazurin
    #     or similar at this step.
    #   * Result: a 96-well 2D color matrix; each well is a unique
    #     red x blue combination.
    def workflow_combinatorial_matrix(plate, plate_idx: int, variant: str):
        wash_mode  = plate_idx >= WASH_TRIGGER_PLATE
        base_ul    = 30
        max_red    = 60   # peak at col 0
        max_blue   = 50   # peak at row H
        indicator  = 20   # yellow, single-channel
        # Max single-well total: 30 + 60 + 50 + 20 = 160 uL (well max 200) ✓

        protocol.comment(
            f"=== Plate {plate_idx + 1} | DOSE-RESPONSE MATRIX ({variant}) ==="
        )

        # 1) Multi-channel: assay buffer base in every column.
        multi_pick_fresh()
        for col in range(N_COLS):
            aspirate_tracked(p300m, base_ul, DILUENT, channels=8)
            dispense_and_lift(p300m, base_ul, plate.columns()[col][0])
        finish_multi(wash_mode)

        # 2) Multi-channel: red gradient across columns (compound A titration).
        multi_pick_fresh()
        for col in range(N_COLS):
            v = round(max_red * (N_COLS - 1 - col) / (N_COLS - 1))
            if v < MIN_DISPENSE_UL:
                continue
            aspirate_tracked(p300m, v, RED, channels=8)
            dispense_and_lift(p300m, v, plate.columns()[col][0])
        finish_multi(wash_mode)

        # 3) Single-channel: blue gradient down rows (compound B titration).
        pick_single_tip("blue")
        for r_idx, row_letter in enumerate("ABCDEFGH"):
            v = round(max_blue * r_idx / (N_ROWS - 1))
            if v < MIN_DISPENSE_UL:
                continue
            for col in range(N_COLS):
                w = plate.wells_by_name()[f"{row_letter}{col + 1}"]
                aspirate_tracked(p300s, v, BLUE)
                dispense_and_lift(p300s, v, w)
        p300s.drop_tip()

        # 4) Single-channel: yellow viability indicator into the experimental
        #    region (everything except outer "border" wells, a common real
        #    layout to avoid edge-effects).
        if variant == "centered":
            target_wells = [
                f"{r}{c + 1}"
                for r in "BCDEFG"   # skip A and H
                for c in range(1, N_COLS - 1)  # skip first and last col
            ]
        else:  # "full"
            target_wells = [f"{r}{c + 1}" for r in "ABCDEFGH" for c in range(N_COLS)]

        pick_single_tip("yellow")
        for w_name in target_wells:
            w = plate.wells_by_name()[w_name]
            aspirate_tracked(p300s, indicator, YELLOW)
            dispense_and_lift(p300s, indicator, w)
        p300s.drop_tip()

    # ----------------------------------------------------------------------
    # Workflow 3: Multiplex Plate Map / Reagent Layout
    # ----------------------------------------------------------------------
    # Real lab practice:
    #   * Each column block is a different "reagent" or "compound family".
    #     This is exactly how a multiplex assay plate or a screening plate
    #     is laid out before adding samples.
    #   * Multi-channel distributes the four "reagents" (R, Y, B, R+B) into
    #     three-column blocks at a uniform volume.
    #   * Single-channel adds defined "positive control" and "negative
    #     control" spots (a typical assay-QC layout).
    #   * Multi-channel tops everything up to a uniform working volume
    #     (volumetric normalization).
    def workflow_multiplex_layout(plate, plate_idx: int, variant: str):
        wash_mode  = plate_idx >= WASH_TRIGGER_PLATE
        reagent_ul = 50    # primary "reagent" volume in each block
        topup_to   = 100   # final working volume after normalization
        control_ul = 25

        protocol.comment(
            f"=== Plate {plate_idx + 1} | MULTIPLEX PLATE MAP ({variant}) ==="
        )

        if variant == "blocks":
            blocks = [
                (RED,    range(0, 3),  False),
                (YELLOW, range(3, 6),  False),
                (BLUE,   range(6, 9),  False),
                (RED,    range(9, 12), True),    # last block = red+blue mix
            ]
        else:  # "stripes" - alternating reagents
            blocks = [
                (RED,    [0, 4, 8],  False),
                (YELLOW, [1, 5, 9],  False),
                (BLUE,   [2, 6, 10], False),
                (RED,    [3, 7, 11], True),
            ]

        # 1) Multi-channel: dispense the primary reagent for each block.
        for lane, cols, needs_overlay in blocks:
            multi_pick_fresh()
            for col in cols:
                aspirate_tracked(p300m, reagent_ul, lane, channels=8)
                dispense_and_lift(p300m, reagent_ul, plate.columns()[col][0])
            finish_multi(wash_mode)
            if needs_overlay:
                # Add a half-volume of blue to make the "mixed reagent" block.
                multi_pick_fresh()
                for col in cols:
                    aspirate_tracked(p300m, reagent_ul // 2, BLUE, channels=8)
                    dispense_and_lift(p300m, reagent_ul // 2, plate.columns()[col][0])
                finish_multi(wash_mode)

        # 2) Single-channel: positive control (high yellow) in row A,
        #    negative control (no addition) in row H - both standard plate
        #    QC layouts.
        pick_single_tip("yellow")
        for col in range(N_COLS):
            w = plate.wells_by_name()[f"A{col + 1}"]
            aspirate_tracked(p300s, control_ul, YELLOW)
            dispense_and_lift(p300s, control_ul, w)
        p300s.drop_tip()

        # 3) Multi-channel: volumetric normalization - top every well up to
        #    a uniform working volume with diluent. Real-lab equivalent of
        #    bringing all samples to the same final volume before reading.
        multi_pick_fresh()
        for col in range(N_COLS):
            col_block = next(
                (b for b in blocks if col in list(b[1])),
                None,
            )
            current = 0
            if col_block is not None:
                current += reagent_ul + (reagent_ul // 2 if col_block[2] else 0)
            topup_each_row = max(0, topup_to - current)
            if topup_each_row < MIN_DISPENSE_UL:
                continue
            aspirate_tracked(p300m, topup_each_row, DILUENT, channels=8)
            dispense_and_lift(p300m, topup_each_row, plate.columns()[col][0])
        finish_multi(wash_mode)

    # ----------------------------------------------------------------------
    # Run sequence
    # ----------------------------------------------------------------------
    #   Plate 1: Serial Dilution  (RYB + purple)
    #   Plate 2: Dose-Response Matrix  (centered indicator)
    #   Plate 3: Multiplex Layout  (column blocks)   <- wash mode kicks in
    #   Plate 4: Serial Dilution  (RYB + orange)
    #   Plate 5: Dose-Response Matrix  (full indicator)
    #   Plate 6: Multiplex Layout  (stripes)
    run_sequence = [
        ("serial",      "RYB+purple"),
        ("matrix",      "centered"),
        ("multiplex",   "blocks"),
        ("serial",      "RYB+orange"),
        ("matrix",      "full"),
        ("multiplex",   "stripes"),
    ]

    workflow_funcs = {
        "serial":    workflow_serial_dilution,
        "matrix":    workflow_combinatorial_matrix,
        "multiplex": workflow_multiplex_layout,
    }

    protocol.home()
    protocol.set_rail_lights(True)   # OT-2 deck lights on for booth visibility

    for i, ((wf_name, variant), plate) in enumerate(zip(run_sequence, plates)):
        workflow_funcs[wf_name](plate, i, variant)

        if incubation_delay_s > 0:
            protocol.delay(
                seconds=incubation_delay_s,
                msg=f"Plate {i + 1}: simulated assay incubation",
            )
        if viewing_delay_s > 0:
            protocol.delay(
                seconds=viewing_delay_s,
                msg=f"Plate {i + 1}: showing finished plate",
            )

    protocol.comment(
        f"Reservoir usage (uL drawn per lane): "
        f"RED={lane_used_ul[RED]}, YELLOW={lane_used_ul[YELLOW]}, "
        f"BLUE={lane_used_ul[BLUE]}, DILUENT={lane_used_ul[DILUENT]}"
    )
    protocol.comment("Demo complete - thanks for visiting the Opentrons booth!")
