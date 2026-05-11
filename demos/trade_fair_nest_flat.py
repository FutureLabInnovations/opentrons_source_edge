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
  * Red, yellow, and blue food coloring (~25 mL each, diluted 1:5 in water
    in their reservoir lanes for vivid but not over-saturated color)
  * Distilled water for the diluent lane and wash station (~250 mL total)

Reservoir layout (NEST 12-well, slot 4):
   A1=red  A2=yellow  A3=blue  A4=diluent (water)  A5..A12=spare/waste

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
        description=(
            "Pause after each finished plate so visitors can admire the "
            "result. Increase to extend total runtime."
        ),
        default=60,
        minimum=0,
        maximum=600,
        unit="s",
    )
    parameters.add_int(
        variable_name="incubation_delay_s",
        display_name="Per-plate incubation delay",
        description=(
            "Mimics a real assay incubation between plates (e.g. letting a "
            "standard curve settle, or a colorimetric reaction develop). "
            "Set to 0 to skip."
        ),
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
        # 3x rinse cycle in the bulk water reservoir, then a blow-out at the
        # surface to clear residual dye.
        for _ in range(3):
            p300m.aspirate(250, wash_station["A1"].bottom(2))
            p300m.dispense(250, wash_station["A1"].top(-3))
        p300m.blow_out(wash_station["A1"].top())

    def finish_multi(wash_mode: bool):
        if wash_mode:
            multi_wash_in_reservoir()
            p300m.return_tip()
        else:
            p300m.drop_tip()

    # ----------------------------------------------------------------------
    # Workflow 1: Serial Dilution / Standard Curve
    # ----------------------------------------------------------------------
    # Real lab practice:
    #   * Load 50 uL of diluent into columns 2-12 (the "dilution wells").
    #   * Load 100 uL of stock sample into column 1, four samples in pairs of
    #     rows: red (A,B), yellow (C,D), blue (E,F), and a red+blue purple
    #     mix (G,H).
    #   * Multi-channel performs a 1:2 serial dilution across columns 1->11,
    #     mixing at each step. Column 12 is left as the blank.
    #   * Result: four horizontal color gradients running across the plate.
    def workflow_serial_dilution(plate, plate_idx: int, variant: str):
        wash_mode = plate_idx >= WASH_TRIGGER_PLATE
        diluent_ul = 50      # pre-loaded diluent in cols 2..12
        stock_ul   = 100     # initial sample volume in col 1
        xfer_ul    = 50      # 1:2 transfer volume
        mix_ul     = 50
        mix_reps   = 3

        protocol.comment(
            f"=== Plate {plate_idx + 1} | SERIAL DILUTION ({variant}) ==="
        )

        # 1) Multi-channel: pre-load diluent into columns 2..12.
        multi_pick_fresh()
        for col in range(1, N_COLS):
            p300m.aspirate(diluent_ul, reservoir[DILUENT])
            p300m.dispense(diluent_ul, plate.columns()[col][0].bottom(2))
        finish_multi(wash_mode)

        # 2) Single-channel: load 4 different stock samples into column 1.
        #    The pair-of-rows layout means each "sample" produces two
        #    identical horizontal gradients (real labs run technical
        #    replicates this way).
        if variant == "RYB+purple":
            sample_layout = [
                ("red",    ["A1", "B1"], stock_ul,  None),
                ("yellow", ["C1", "D1"], stock_ul,  None),
                ("blue",   ["E1", "F1"], stock_ul,  None),
                # Purple = half-stock red then half-stock blue (mixed below).
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
                p300s.aspirate(vol, reservoir[color_to_lane[color]])
                p300s.dispense(vol, plate.wells_by_name()[w].bottom(2))
            p300s.drop_tip()
            if follow_up == "blue_addition":
                pick_single_tip("blue")
                for w in wells:
                    p300s.aspirate(stock_ul // 2, reservoir[BLUE])
                    p300s.dispense(stock_ul // 2, plate.wells_by_name()[w].bottom(2))
                    p300s.mix(2, mix_ul, plate.wells_by_name()[w].bottom(2))
                p300s.drop_tip()
            elif follow_up == "yellow_addition":
                pick_single_tip("yellow")
                for w in wells:
                    p300s.aspirate(stock_ul // 2, reservoir[YELLOW])
                    p300s.dispense(stock_ul // 2, plate.wells_by_name()[w].bottom(2))
                    p300s.mix(2, mix_ul, plate.wells_by_name()[w].bottom(2))
                p300s.drop_tip()

        # 3) Multi-channel: 1:2 serial dilution across columns 1 -> 11.
        #    A new pair of tips for the dilution (these will see all four
        #    sample colors, so cannot be re-used for any other color step).
        multi_pick_fresh()
        for col in range(N_COLS - 2):  # transfers from col 0..10 into col 1..11
            src = plate.columns()[col][0].bottom(2)
            dst = plate.columns()[col + 1][0].bottom(2)
            p300m.aspirate(xfer_ul, src)
            p300m.dispense(xfer_ul, dst)
            p300m.mix(mix_reps, mix_ul, dst)
            p300m.blow_out(dst.top(-2))
        # Final tip-off: dilution tips are saturated with mixed dye, so
        # don't return to rack even in wash mode.
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
            p300m.aspirate(base_ul, reservoir[DILUENT])
            p300m.dispense(base_ul, plate.columns()[col][0].bottom(2))
        finish_multi(wash_mode)

        # 2) Multi-channel: red gradient across columns (compound A titration).
        multi_pick_fresh()
        for col in range(N_COLS):
            v = round(max_red * (N_COLS - 1 - col) / (N_COLS - 1))
            if v < MIN_DISPENSE_UL:
                continue
            p300m.aspirate(v, reservoir[RED])
            p300m.dispense(v, plate.columns()[col][0].bottom(2))
        finish_multi(wash_mode)

        # 3) Single-channel: blue gradient down rows (compound B titration).
        pick_single_tip("blue")
        for r_idx, row_letter in enumerate("ABCDEFGH"):
            v = round(max_blue * r_idx / (N_ROWS - 1))
            if v < MIN_DISPENSE_UL:
                continue
            for col in range(N_COLS):
                w = plate.wells_by_name()[f"{row_letter}{col + 1}"]
                p300s.aspirate(v, reservoir[BLUE])
                p300s.dispense(v, w.bottom(2))
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
            p300s.aspirate(indicator, reservoir[YELLOW])
            p300s.dispense(indicator, w.bottom(2))
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
                p300m.aspirate(reagent_ul, reservoir[lane])
                p300m.dispense(reagent_ul, plate.columns()[col][0].bottom(2))
            finish_multi(wash_mode)
            if needs_overlay:
                # Add a half-volume of blue to make the "mixed reagent" block.
                multi_pick_fresh()
                for col in cols:
                    p300m.aspirate(reagent_ul // 2, reservoir[BLUE])
                    p300m.dispense(reagent_ul // 2, plate.columns()[col][0].bottom(2))
                finish_multi(wash_mode)

        # 2) Single-channel: positive control (high yellow) in row A,
        #    negative control (no addition) in row H - both standard plate
        #    QC layouts.
        pick_single_tip("yellow")
        for col in range(N_COLS):
            w = plate.wells_by_name()[f"A{col + 1}"]
            p300s.aspirate(control_ul, reservoir[YELLOW])
            p300s.dispense(control_ul, w.bottom(2))
        p300s.drop_tip()

        # 3) Multi-channel: volumetric normalization - top every well up to
        #    a uniform working volume with diluent. Real-lab equivalent of
        #    bringing all samples to the same final volume before reading.
        multi_pick_fresh()
        for col in range(N_COLS):
            # Estimate current volume per well in this column. Wells in
            # column-blocks got `reagent_ul` (plus maybe overlay). Row A also
            # got a control_ul addition.
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
            p300m.aspirate(topup_each_row, reservoir[DILUENT])
            p300m.dispense(topup_each_row, plate.columns()[col][0].bottom(2))
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

    protocol.comment("Demo complete - thanks for visiting the Opentrons booth!")
