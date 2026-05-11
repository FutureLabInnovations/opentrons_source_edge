"""
OT-2 Trade Fair Demo  -  "Painted Lab"
======================================

Autonomous ~2-hour OT-2 demo that turns six 96-well plates into six
visually distinct mini-experiments. Built around the same proven
volume math as our internal RGYB serial-dilution protocol
(150 uL stock / 75 uL diluent / 75 uL transfer / 4x mix(75)) but with
a different choreography per plate so the booth never shows the same
movement twice in a row.

Plates (in run order):
  1. **Standard Curves**         - four horizontal 1:2 serial-dilution
                                    gradients on one plate (real-lab
                                    standard-curve prep, 4 colours).
  2. **Synergy Matrix**          - 2D dose-response heat-map: red
                                    titrated across the columns, blue
                                    titrated down the rows, yellow
                                    viability indicator in the
                                    experimental zone (Bliss/Loewe
                                    checkerboard layout).
  3. **Multiplex Plate Map**     - four solid-colour column blocks
                                    (red, yellow, blue, green=Y+B),
                                    the way a multiplex assay or
                                    compound library is laid out
                                    before adding samples.
  4. **ELISA Plate Layout**      - cols 1-2 standard curve in red
                                    (vertical 1:2 dilution), cols 3-10
                                    "patient samples" with varying
                                    intensities, col 11 positive
                                    control (yellow), col 12 NTC
                                    blank.
  5. **Mixed-Colour Bouquet**    - four mixed-colour row pairs
                                    (orange=R+Y, green=Y+B,
                                    purple=R+B, brown=R+Y+B) each
                                    serial-diluted across the plate.
  6. **Concentric Rainbow Rings**- single-channel finale: four nested
                                    rings of pure colour radiating
                                    inward (red, yellow, green, blue)
                                    - the "showpiece" plate.

Pipettes (no modules used):
  - left  : P300 Single-Channel GEN2  -> sample loading, controls, painting
  - right : P300 Multi-Channel  GEN2  -> bulk fills, serial dilution

Tip strategy (real-lab practice):
  Single-channel rack is sectioned by reagent so a tip never sees more
  than one colour:
      cols 1-3  -> red tips
      cols 4-6  -> yellow tips
      cols 7-9  -> blue tips
      cols 10-12-> wash/water tips
  Multi-channel uses fresh tip columns for the first WASH_TRIGGER_PLATE
  plates, then switches to wash-and-reuse mode (mix(4, 250) in the
  bulk reservoir between colours, returned to the rack for re-use).

Liquids are registered with protocol.define_liquid() and assigned to
their starting wells with well.load_liquid(), so the Opentrons app
shows the booth crew exactly what to load and where during setup.

==============================================================================
MATERIALS  (everything you need at the booth)
==============================================================================

Hardware (already on the robot):
  * Opentrons OT-2
  * P300 Multi-Channel GEN2  (right mount)
  * P300 Single-Channel GEN2 (left mount)

Labware (load names are the exact strings the OT-2 will look up):
  * 6 x thermofisher_96_wellplate_250ul   (custom labware - the 250 uL
        ThermoFisher 96-well plate your robot already has uploaded; same
        load name the internal RGYB serial-dilution protocol uses.
        Slots 2, 5, 6, 7, 8, 11.)
  * 1 x nest_12_reservoir_15ml            (slot 4: dyes + diluent + wash)
  * 3 x opentrons_96_tiprack_300ul        (slots 1, 3, 10)
  * slot 9 is left empty

Consumables to prepare before starting:
  * Red food colouring   - dilute 1:5 in water -> pour ~10 mL into res A1
  * Yellow food colouring- dilute 1:5 in water -> pour ~10 mL into res A2
  * Blue food colouring  - dilute 1:5 in water -> pour ~10 mL into res A3
  * Distilled water - pour ~12 mL each into lanes A4, A5, A6 (3 diluent
                     lanes; the protocol auto-rotates as each fills up).
  * Distilled water - pour ~12 mL into lane A12 (multi-channel tip wash).
  * Total water needed: ~48 mL. No 50 mL Falcon tubes or bulk reservoirs
    needed - everything lives in the single 12-channel reservoir.

Optional but recommended for booth impact:
  * A white sheet or LED light pad under the OT-2 deck. The plates light
    up beautifully and gradients read from across the room.
  * A printed placard explaining what visitors are seeing.

No 15 mL or 50 mL Falcon tube adapter is required - the protocol does
not use tubes anywhere.

==============================================================================
SETUP INSTRUCTIONS  (in the order the Opentrons app will walk you through)
==============================================================================

  1. Mount the P300 Single GEN2 on the LEFT mount and the
     P300 Multi GEN2 on the RIGHT mount.
  2. Calibrate the deck and pipettes if the app prompts you.
  3. Load the three opentrons_96_tiprack_300ul racks into slots 1, 3, 10.
       slot 1  = single-channel tips (will be sectioned by colour - just
                 a full rack of tips; the protocol manages which tips
                 it picks for which dye)
       slots 3 & 10 = multi-channel tip reservoirs (full racks)
  4. Load the NEST 12-channel reservoir (nest_12_reservoir_15ml) into
     slot 4. Slot 9 stays empty.
  5. **In the Liquid Setup screen of the Opentrons app**, confirm:
       slot 4 well A1   -> Red Dye      (~10 mL)
       slot 4 well A2   -> Yellow Dye   (~10 mL)
       slot 4 well A3   -> Blue Dye     (~10 mL)
       slot 4 wells A4-A6 -> Diluent Water (~12 mL each, 3 lanes)
       slot 4 well A12  -> Wash Water   (~12 mL)
     Each liquid is registered by the protocol with a display colour so
     the app shows a coloured swatch for each lane.
  6. Load 6 empty thermofisher_96_wellplate_250ul plates into slots
     2, 5, 6, 7, 8 and 11. (This is the custom labware definition you
     have uploaded to the OT-2; the app will recognise the load name.)
  7. (Optional) Tune the two runtime parameters in the app:
       * Per-plate viewing delay   - default 60 s
       * Per-plate incubation delay- default 180 s
     Increase both to lengthen the show; decrease to compress.
  8. Hit "Start run" - total runtime is ~2 hours.
"""

from opentrons import protocol_api

metadata = {
    "protocolName": "Trade Fair - Painted Lab",
    "author": "Opentrons Demo",
    "description": (
        "Six 96-well plates, six lab-style colour workflows. Built on the "
        "proven 150/75/75 uL serial-dilution math but with distinct "
        "choreography per plate. Liquids are registered for app setup."
    ),
}

# 2.18+ is required for runtime parameters (add_parameters / protocol.params).
# define_liquid() and load_liquid() are available from 2.14+, so 2.18 covers both.
requirements = {"robotType": "OT-2", "apiLevel": "2.18"}


# ---------------------------------------------------------------------------
# Tunables
# ---------------------------------------------------------------------------

# NEST 12-channel reservoir lane assignments.
# Dyes live in A1-A3. Diluent water is split across THREE lanes (A4-A6) so
# the protocol can rotate to the next lane as each ~12 mL fill runs out;
# A12 is the dedicated wash lane (gradually picks up trace dye over the
# course of the run, which is fine because nothing is ever drawn from it).
RED_LANE, YELLOW_LANE, BLUE_LANE = "A1", "A2", "A3"
DILUENT_LANES = ["A4", "A5", "A6"]
WASH_LANE     = "A12"

# Safe usable volume per 12-channel reservoir lane (mL spec is 15 mL, we
# leave a small headroom so the multi-channel never pulls air).
LANE_USABLE_UL = 12_000

# Single-channel tip-rack sections (1-indexed column ranges, inclusive).
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

# Plate geometry. thermofisher_96_wellplate_250ul is the custom 250 uL
# 96-well labware definition uploaded to the OT-2 (same load name the
# lab's internal RGYB serial-dilution protocol uses).
PLATE_LOAD_NAME = "thermofisher_96_wellplate_250ul"
N_ROWS, N_COLS  = 8, 12

# Proven serial-dilution volume math (from the lab's internal protocol).
STOCK_UL    = 150
DILUENT_UL  = 75
XFER_UL     = 75
MIX_UL      = 75
MIX_REPS    = 4

# Sub-stock volumes for two- and three-colour mixes (so stock col 1 still
# ends up at 150 uL total, matching the proven dilution math).
HALF_STOCK_UL  = STOCK_UL // 2   # 75 uL for two-colour mixes (75 + 75 = 150)
THIRD_STOCK_UL = STOCK_UL // 3   # 50 uL for three-colour mixes (50*3 = 150)


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
        default=180,
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

    # =====================================================================
    # Liquid definitions (shown in the app's Liquid Setup screen)
    # =====================================================================
    red_dye = protocol.define_liquid(
        name="Red Dye",
        description=(
            "Red food colouring diluted 1:5 in distilled water. "
            "Pour ~12 mL into reservoir lane A1 before starting."
        ),
        display_color="#e60026",
    )
    yellow_dye = protocol.define_liquid(
        name="Yellow Dye",
        description=(
            "Yellow food colouring diluted 1:5 in distilled water. "
            "Pour ~12 mL into reservoir lane A2 before starting."
        ),
        display_color="#ffd400",
    )
    blue_dye = protocol.define_liquid(
        name="Blue Dye",
        description=(
            "Blue food colouring diluted 1:5 in distilled water. "
            "Pour ~12 mL into reservoir lane A3 before starting."
        ),
        display_color="#0066cc",
    )
    diluent_water = protocol.define_liquid(
        name="Diluent Water",
        description=(
            "Distilled water. Serial-dilution buffer. Pour ~12 mL into "
            "EACH of lanes A4, A5, A6 (the protocol auto-rotates lanes "
            "as they empty)."
        ),
        display_color="#bfe6ff",
    )
    wash_water = protocol.define_liquid(
        name="Wash Water",
        description=(
            "Distilled water for multi-channel tip rinsing between "
            "colours. Pour ~12 mL into lane A12. Stays in place for the "
            "whole run."
        ),
        display_color="#cccccc",
    )

    # =====================================================================
    # Labware
    # =====================================================================
    reservoir = protocol.load_labware("nest_12_reservoir_15ml", 4)

    plates = [
        protocol.load_labware(PLATE_LOAD_NAME, slot, f"plate {i + 1}")
        for i, slot in enumerate([2, 5, 6, 7, 8, 11])
    ]

    rack_single  = protocol.load_labware("opentrons_96_tiprack_300ul", 1, "single tips")
    rack_multi_a = protocol.load_labware("opentrons_96_tiprack_300ul", 3, "multi tips A")
    rack_multi_b = protocol.load_labware("opentrons_96_tiprack_300ul", 10, "multi tips B")

    # Tell the app where each liquid starts; the app draws a coloured swatch.
    reservoir[RED_LANE].load_liquid(red_dye, 10_000)
    reservoir[YELLOW_LANE].load_liquid(yellow_dye, 10_000)
    reservoir[BLUE_LANE].load_liquid(blue_dye, 10_000)
    for lane in DILUENT_LANES:
        reservoir[lane].load_liquid(diluent_water, LANE_USABLE_UL)
    reservoir[WASH_LANE].load_liquid(wash_water, LANE_USABLE_UL)

    # =====================================================================
    # Pipettes
    # =====================================================================
    p300s = protocol.load_instrument("p300_single_gen2", "left",
                                     tip_racks=[rack_single])
    p300m = protocol.load_instrument("p300_multi_gen2",  "right",
                                     tip_racks=[rack_multi_a, rack_multi_b])

    p300s.flow_rate.aspirate = 100
    p300s.flow_rate.dispense = 200
    p300m.flow_rate.aspirate = 100
    p300m.flow_rate.dispense = 200

    # =====================================================================
    # Source mapping & volume tracking
    # =====================================================================
    # Spiritual descendant of the proven protocol's TubeTracker, minus the
    # cone math (NEST troughs are flat). Any draw beyond the lane cap
    # aborts the run with a clear message instead of aspirating air.
    sources = {
        "red":    reservoir[RED_LANE],
        "yellow": reservoir[YELLOW_LANE],
        "blue":   reservoir[BLUE_LANE],
    }
    caps_ul = {"red": 10_000, "yellow": 10_000, "blue": 10_000}
    used_ul = {k: 0 for k in caps_ul}

    def aspirate_tracked(pipette, vol_ul: int, lane: str, channels: int = 1):
        # For dye lanes (red / yellow / blue) - single lane each, hard cap.
        draw_ul = vol_ul * channels
        if used_ul[lane] + draw_ul > caps_ul[lane]:
            raise RuntimeError(
                f"Source '{lane}' would be exhausted "
                f"(used {used_ul[lane]} uL, attempting {draw_ul} uL more, "
                f"cap {caps_ul[lane]} uL)."
            )
        used_ul[lane] += draw_ul
        pipette.aspirate(vol_ul, sources[lane])

    # Diluent water lives in *multiple* lanes (A4-A6). The protocol
    # auto-rotates as each lane fills up - same idea as the proven
    # protocol's TubeTracker stop-before-air check, but applied across a
    # bank of lanes so we have ~36 mL of water without needing a bulk
    # reservoir on slot 9.
    diluent_used = {lane: 0 for lane in DILUENT_LANES}
    diluent_idx  = [0]   # mutable, index into DILUENT_LANES

    def aspirate_diluent(pipette, vol_ul: int, channels: int = 1):
        draw_ul = vol_ul * channels
        while diluent_idx[0] < len(DILUENT_LANES):
            lane = DILUENT_LANES[diluent_idx[0]]
            if diluent_used[lane] + draw_ul <= LANE_USABLE_UL:
                diluent_used[lane] += draw_ul
                pipette.aspirate(vol_ul, reservoir[lane])
                return
            # current diluent lane full; advance to the next
            diluent_idx[0] += 1
        raise RuntimeError(
            "Diluent exhausted across all "
            f"{len(DILUENT_LANES)} lanes; refill A4-A6 with more water."
        )

    def dispense_and_lift(pipette, vol_ul: int, well, lift_z: int = -2):
        # Proven touch-off-without-touch-tip: dispense above the surface
        # (well.top(z=-5)), then hover at top(z=lift_z) so any hanging
        # droplet drops into the well instead of being dragged.
        pipette.dispense(vol_ul, well.top(z=-5))
        pipette.move_to(well.top(z=lift_z))

    # =====================================================================
    # Tip helpers (sectioned single-channel + multi-channel wash & reuse)
    # =====================================================================
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

    def multi_wash():
        # mix(4, 250) is the proven internal-protocol wash pattern. Wash
        # water lives in the dedicated A12 lane - it slowly picks up
        # trace dye over the run, but nothing is ever drawn from it, so
        # contamination stays inside that one lane.
        wash_well = reservoir[WASH_LANE]
        p300m.mix(4, 250, wash_well.bottom(2))
        p300m.blow_out(wash_well.top(-3))

    def finish_multi(wash_mode: bool):
        if wash_mode:
            multi_wash()
            p300m.return_tip()
        else:
            p300m.drop_tip()

    # =====================================================================
    # Common building blocks
    # =====================================================================
    def multi_prefill_diluent(plate, first_col: int, last_col_exclusive: int,
                              vol_per_col: int, wash_mode: bool):
        """Multi-channel: pre-load `vol_per_col` of water into each
        column in [first_col, last_col_exclusive). All 8 rows of each
        column fill in one shot."""
        multi_pick_fresh()
        for col in range(first_col, last_col_exclusive):
            aspirate_diluent(p300m, vol_per_col, channels=8)
            dispense_and_lift(p300m, vol_per_col, plate.columns()[col][0])
        finish_multi(wash_mode)

    def multi_serial_dilute(plate, first_col: int, last_col_exclusive: int):
        """Multi-channel 1:2 serial dilution across [first_col,
        last_col_exclusive). Tips are sacrificed at the end (they have
        seen every colour in the column-1 stocks)."""
        multi_pick_fresh()
        for col in range(first_col, last_col_exclusive - 1):
            src = plate.columns()[col][0].bottom(2)
            dst = plate.columns()[col + 1][0].bottom(2)
            p300m.aspirate(XFER_UL, src)
            p300m.dispense(XFER_UL, dst)
            p300m.mix(MIX_REPS, MIX_UL, dst)
            p300m.blow_out(plate.columns()[col + 1][0].top(z=-2))
        p300m.drop_tip()

    def single_dispense_color(color: str, lane: str, wells, vol_ul: int,
                              mix_after: bool = False):
        """Single-channel: pick a tip from `color`'s section, dispense
        `vol_ul` of `lane` into each well, optionally mix the last
        well, then drop the tip."""
        pick_single_tip(color)
        for w in wells:
            target = w if hasattr(w, "top") else plate_lookup(w)
            aspirate_tracked(p300s, vol_ul, lane)
            if mix_after and w is wells[-1]:
                p300s.dispense(vol_ul, target.bottom(2))
                p300s.mix(2, MIX_UL, target.bottom(2))
                p300s.move_to(target.top(z=-2))
            else:
                dispense_and_lift(p300s, vol_ul, target)
        p300s.drop_tip()

    # tiny inline helper for the workflows below
    def plate_lookup(_):  # pragma: no cover - placeholder, never called
        raise RuntimeError("single_dispense_color was passed a non-Well")

    # =====================================================================
    # WORKFLOW 1: Standard Curves (four horizontal 1:2 dilution gradients)
    # =====================================================================
    # Real lab analog: parallel standard-curve preparation, four samples
    # done in technical-duplicate row pairs (A/B, C/D, E/F, G/H).
    def plate_standard_curves(plate, plate_idx: int):
        wash_mode = plate_idx >= WASH_TRIGGER_PLATE
        protocol.comment(
            f"=== Plate {plate_idx + 1} | STANDARD CURVES (4 colours) ==="
        )

        # 1) Multi-channel: water in cols 2..12.
        multi_prefill_diluent(plate, 1, N_COLS, DILUENT_UL, wash_mode)

        # 2) Single-channel: four stocks into column 1 (row pairs).
        col1 = {"A": plate["A1"], "B": plate["B1"], "C": plate["C1"],
                "D": plate["D1"], "E": plate["E1"], "F": plate["F1"],
                "G": plate["G1"], "H": plate["H1"]}

        # Pure-colour stocks: red A/B, yellow C/D, blue E/F.
        for tip_color, lane, wells in [
            ("red",    "red",    [col1["A"], col1["B"]]),
            ("yellow", "yellow", [col1["C"], col1["D"]]),
            ("blue",   "blue",   [col1["E"], col1["F"]]),
        ]:
            pick_single_tip(tip_color)
            for w in wells:
                aspirate_tracked(p300s, STOCK_UL, lane)
                dispense_and_lift(p300s, STOCK_UL, w)
            p300s.drop_tip()

        # Purple (R + B) into G/H: red half first, then blue half + mix.
        pick_single_tip("red")
        for w in (col1["G"], col1["H"]):
            aspirate_tracked(p300s, HALF_STOCK_UL, "red")
            p300s.dispense(HALF_STOCK_UL, w.bottom(2))
        p300s.drop_tip()
        pick_single_tip("blue")
        for w in (col1["G"], col1["H"]):
            aspirate_tracked(p300s, HALF_STOCK_UL, "blue")
            p300s.dispense(HALF_STOCK_UL, w.bottom(2))
            p300s.mix(2, MIX_UL, w.bottom(2))
            p300s.move_to(w.top(z=-2))
        p300s.drop_tip()

        # 3) Multi-channel: 1:2 serial dilution cols 1..11 (col 12 blank).
        multi_serial_dilute(plate, 0, N_COLS - 1)

    # =====================================================================
    # WORKFLOW 2: Synergy Matrix (2D dose-response checkerboard)
    # =====================================================================
    # Real lab analog: Bliss / Loewe drug-synergy checkerboard. Compound A
    # (red) titrated across columns; compound B (blue) titrated down rows;
    # yellow viability indicator added in the experimental zone.
    def plate_synergy_matrix(plate, plate_idx: int):
        wash_mode = plate_idx >= WASH_TRIGGER_PLATE
        base_ul   = 30   # assay-buffer base
        max_red   = 60   # peak at col 0
        max_blue  = 50   # peak at row H
        indicator = 20   # yellow

        protocol.comment(
            f"=== Plate {plate_idx + 1} | SYNERGY MATRIX (2D dose-response) ==="
        )

        # 1) Multi-channel: assay-buffer base in every column.
        multi_pick_fresh()
        for col in range(N_COLS):
            aspirate_diluent(p300m, base_ul, channels=8)
            dispense_and_lift(p300m, base_ul, plate.columns()[col][0])
        finish_multi(wash_mode)

        # 2) Multi-channel: red gradient across columns.
        multi_pick_fresh()
        for col in range(N_COLS):
            v = round(max_red * (N_COLS - 1 - col) / (N_COLS - 1))
            if v < MIN_DISPENSE_UL:
                continue
            aspirate_tracked(p300m, v, "red", channels=8)
            dispense_and_lift(p300m, v, plate.columns()[col][0])
        finish_multi(wash_mode)

        # 3) Single-channel: blue gradient down rows.
        pick_single_tip("blue")
        for r_idx, row_letter in enumerate("ABCDEFGH"):
            v = round(max_blue * r_idx / (N_ROWS - 1))
            if v < MIN_DISPENSE_UL:
                continue
            for col in range(N_COLS):
                w = plate.wells_by_name()[f"{row_letter}{col + 1}"]
                aspirate_tracked(p300s, v, "blue")
                dispense_and_lift(p300s, v, w)
        p300s.drop_tip()

        # 4) Single-channel: yellow indicator in the central experimental
        #    zone (skip A/H rows and 1/12 columns, the classic "edge-
        #    effect" exclusion).
        pick_single_tip("yellow")
        for r in "BCDEFG":
            for c in range(1, N_COLS - 1):
                w = plate.wells_by_name()[f"{r}{c + 1}"]
                aspirate_tracked(p300s, indicator, "yellow")
                dispense_and_lift(p300s, indicator, w)
        p300s.drop_tip()

    # =====================================================================
    # WORKFLOW 3: Multiplex Plate Map (four solid-colour column blocks)
    # =====================================================================
    # Real lab analog: assay-plate layout for a 4-condition multiplex or
    # a compound-library plate map. Each three-column block represents a
    # different reagent / compound family.
    def plate_multiplex_blocks(plate, plate_idx: int):
        wash_mode = plate_idx >= WASH_TRIGGER_PLATE
        block_ul  = 80    # primary reagent volume in each well

        protocol.comment(
            f"=== Plate {plate_idx + 1} | MULTIPLEX PLATE MAP (4 blocks) ==="
        )

        blocks = [
            ("red",     "red",    range(0, 3),  None),
            ("yellow",  "yellow", range(3, 6),  None),
            ("blue",    "blue",   range(6, 9),  None),
            ("yellow",  "yellow", range(9, 12), "blue_overlay"),  # -> green
        ]

        for tip_label, lane, cols, overlay in blocks:
            multi_pick_fresh()
            for col in cols:
                aspirate_tracked(p300m, block_ul, lane, channels=8)
                dispense_and_lift(p300m, block_ul, plate.columns()[col][0])
            finish_multi(wash_mode)
            if overlay == "blue_overlay":
                # Y + B = green
                multi_pick_fresh()
                for col in cols:
                    aspirate_tracked(p300m, block_ul, "blue", channels=8)
                    dispense_and_lift(p300m, block_ul, plate.columns()[col][0])
                finish_multi(wash_mode)

    # =====================================================================
    # WORKFLOW 4: ELISA Plate Layout
    # =====================================================================
    # Real lab analog: textbook ELISA plate. Cols 1-2 are duplicate
    # standard-curve points (8 standards per column, top->bottom
    # 1:2 dilution series). Cols 3-10 are "patient samples" with varying
    # intensity. Col 11 is the positive control (high yellow). Col 12
    # is the no-template / blank control.
    def plate_elisa_layout(plate, plate_idx: int):
        wash_mode = plate_idx >= WASH_TRIGGER_PLATE
        std_col_stock_ul   = 100   # red stock in row A of cols 1 & 2
        std_dil_ul         = 50
        std_xfer_ul        = 50
        sample_base_ul     = 60    # diluent in sample cols
        pos_ctrl_ul        = 80    # yellow in col 11
        blank_ul           = 80    # water in col 12

        protocol.comment(
            f"=== Plate {plate_idx + 1} | ELISA LAYOUT (standard+samples+ctrls) ==="
        )

        # 1) Single-channel vertical standard curves in cols 1 & 2.
        #    Diluent in rows B-H of cols 1-2 first, then stock in A1/A2,
        #    then top->bottom 1:2 dilution.
        pick_single_tip("wash")
        for col_letter in ("1", "2"):
            for row in "BCDEFGH":
                w = plate.wells_by_name()[f"{row}{col_letter}"]
                aspirate_diluent(p300s, std_dil_ul)
                dispense_and_lift(p300s, std_dil_ul, w)
        p300s.drop_tip()

        pick_single_tip("red")
        for col_letter in ("1", "2"):
            top_well = plate.wells_by_name()[f"A{col_letter}"]
            aspirate_tracked(p300s, std_col_stock_ul, "red")
            dispense_and_lift(p300s, std_col_stock_ul, top_well)
        # 1:2 vertical dilution down each std column.
        for col_letter in ("1", "2"):
            for r_idx in range(N_ROWS - 1):
                src = plate.wells_by_name()[f"{'ABCDEFGH'[r_idx]}{col_letter}"]
                dst = plate.wells_by_name()[f"{'ABCDEFGH'[r_idx + 1]}{col_letter}"]
                p300s.aspirate(std_xfer_ul, src.bottom(2))
                p300s.dispense(std_xfer_ul, dst.bottom(2))
                p300s.mix(2, std_xfer_ul, dst.bottom(2))
                p300s.move_to(dst.top(z=-2))
        p300s.drop_tip()

        # 2) Multi-channel diluent base in cols 3-10 (the sample region).
        multi_pick_fresh()
        for col in range(2, 10):
            aspirate_diluent(p300m, sample_base_ul, channels=8)
            dispense_and_lift(p300m, sample_base_ul, plate.columns()[col][0])
        finish_multi(wash_mode)

        # 3) Single-channel "sample" pattern: red dye spotted at varying
        #    volumes that look like real biological variability (a few
        #    bright "positive" samples, several mid-range, some near-blank).
        sample_pattern = {  # well_name -> uL of red
            "A3":  60, "B3":  40, "C3":  25, "D3":  70, "E3":  20, "F3":  35, "G3":  25, "H3":  30,
            "A4":  35, "B4":  55, "C4":  30, "D4":  20, "E4":  40, "F4":  60, "G4":  30, "H4":  20,
            "A5":  20, "B5":  25, "C5":  50, "D5":  40, "E5":  30, "F5":  20, "G5":  40, "H5":  35,
            "A6":  45, "B6":  30, "C6":  20, "D6":  60, "E6":  35, "F6":  30, "G6":  50, "H6":  25,
            "A7":  25, "B7":  60, "C7":  40, "D7":  30, "E7":  55, "F7":  25, "G7":  30, "H7":  40,
            "A8":  30, "B8":  35, "C8":  25, "D8":  50, "E8":  20, "F8":  40, "G8":  35, "H8":  20,
            "A9":  40, "B9":  20, "C9":  60, "D9":  25, "E9":  30, "F9":  50, "G9":  20, "H9":  30,
            "A10": 25, "B10": 45, "C10": 35, "D10": 30, "E10": 25, "F10": 40, "G10": 30, "H10": 25,
        }
        pick_single_tip("red")
        for w_name, vol in sample_pattern.items():
            if vol < MIN_DISPENSE_UL:
                continue
            w = plate.wells_by_name()[w_name]
            aspirate_tracked(p300s, vol, "red")
            dispense_and_lift(p300s, vol, w)
        p300s.drop_tip()

        # 4) Multi-channel: positive control (yellow) in col 11.
        multi_pick_fresh()
        aspirate_tracked(p300m, pos_ctrl_ul, "yellow", channels=8)
        dispense_and_lift(p300m, pos_ctrl_ul, plate.columns()[10][0])
        finish_multi(wash_mode)

        # 5) Multi-channel: NTC blank (water) in col 12.
        multi_pick_fresh()
        aspirate_diluent(p300m, blank_ul, channels=8)
        dispense_and_lift(p300m, blank_ul, plate.columns()[11][0])
        finish_multi(wash_mode)

    # =====================================================================
    # WORKFLOW 5: Mixed-Colour Bouquet (four mixed-colour row-pair curves)
    # =====================================================================
    # Real lab analog: parallel standard curves of mixed-reagent samples
    # (e.g. comparing two-component formulations). Each row pair is a
    # different secondary colour formed by mixing two or three primaries
    # in column 1, then 1:2 serial-diluted out to column 12.
    def plate_mixed_bouquet(plate, plate_idx: int):
        wash_mode = plate_idx >= WASH_TRIGGER_PLATE
        protocol.comment(
            f"=== Plate {plate_idx + 1} | MIXED-COLOUR BOUQUET "
            f"(orange/green/purple/brown) ==="
        )

        # 1) Diluent in cols 2..12.
        multi_prefill_diluent(plate, 1, N_COLS, DILUENT_UL, wash_mode)

        # 2) Mix four secondary colours into column 1 (row pairs).
        ab = (plate["A1"], plate["B1"])
        cd = (plate["C1"], plate["D1"])
        ef = (plate["E1"], plate["F1"])
        gh = (plate["G1"], plate["H1"])

        # Orange (A,B) = red + yellow
        pick_single_tip("red")
        for w in ab:
            aspirate_tracked(p300s, HALF_STOCK_UL, "red")
            p300s.dispense(HALF_STOCK_UL, w.bottom(2))
        p300s.drop_tip()
        pick_single_tip("yellow")
        for w in ab:
            aspirate_tracked(p300s, HALF_STOCK_UL, "yellow")
            p300s.dispense(HALF_STOCK_UL, w.bottom(2))
            p300s.mix(2, MIX_UL, w.bottom(2))
            p300s.move_to(w.top(z=-2))
        p300s.drop_tip()

        # Green (C,D) = yellow + blue
        pick_single_tip("yellow")
        for w in cd:
            aspirate_tracked(p300s, HALF_STOCK_UL, "yellow")
            p300s.dispense(HALF_STOCK_UL, w.bottom(2))
        p300s.drop_tip()
        pick_single_tip("blue")
        for w in cd:
            aspirate_tracked(p300s, HALF_STOCK_UL, "blue")
            p300s.dispense(HALF_STOCK_UL, w.bottom(2))
            p300s.mix(2, MIX_UL, w.bottom(2))
            p300s.move_to(w.top(z=-2))
        p300s.drop_tip()

        # Purple (E,F) = red + blue
        pick_single_tip("red")
        for w in ef:
            aspirate_tracked(p300s, HALF_STOCK_UL, "red")
            p300s.dispense(HALF_STOCK_UL, w.bottom(2))
        p300s.drop_tip()
        pick_single_tip("blue")
        for w in ef:
            aspirate_tracked(p300s, HALF_STOCK_UL, "blue")
            p300s.dispense(HALF_STOCK_UL, w.bottom(2))
            p300s.mix(2, MIX_UL, w.bottom(2))
            p300s.move_to(w.top(z=-2))
        p300s.drop_tip()

        # Brown (G,H) = red + yellow + blue (50 uL each = 150 uL stock)
        pick_single_tip("red")
        for w in gh:
            aspirate_tracked(p300s, THIRD_STOCK_UL, "red")
            p300s.dispense(THIRD_STOCK_UL, w.bottom(2))
        p300s.drop_tip()
        pick_single_tip("yellow")
        for w in gh:
            aspirate_tracked(p300s, THIRD_STOCK_UL, "yellow")
            p300s.dispense(THIRD_STOCK_UL, w.bottom(2))
        p300s.drop_tip()
        pick_single_tip("blue")
        for w in gh:
            aspirate_tracked(p300s, THIRD_STOCK_UL, "blue")
            p300s.dispense(THIRD_STOCK_UL, w.bottom(2))
            p300s.mix(2, MIX_UL, w.bottom(2))
            p300s.move_to(w.top(z=-2))
        p300s.drop_tip()

        # 3) Multi-channel: serial dilution cols 1..11 (col 12 blank).
        multi_serial_dilute(plate, 0, N_COLS - 1)

    # =====================================================================
    # WORKFLOW 6: Concentric Rainbow Rings (single-channel finale)
    # =====================================================================
    # The showpiece. Four nested rings of pure colour radiating inward.
    # Single-channel paints every well one at a time - slow but
    # mesmerising to watch, and a great closing "wow" plate.
    def plate_concentric_rings(plate, plate_idx: int):
        protocol.comment(
            f"=== Plate {plate_idx + 1} | CONCENTRIC RAINBOW RINGS (finale) ==="
        )

        # Build the four nested ring sets.
        rows_alpha = "ABCDEFGH"
        rings = []
        n_rings = min(N_ROWS, N_COLS) // 2   # = 4 for an 8x12 plate
        for k in range(n_rings):
            wells = []
            for c in range(k, N_COLS - k):
                wells.append(f"{rows_alpha[k]}{c + 1}")
                wells.append(f"{rows_alpha[N_ROWS - 1 - k]}{c + 1}")
            for r in range(k + 1, N_ROWS - 1 - k):
                wells.append(f"{rows_alpha[r]}{k + 1}")
                wells.append(f"{rows_alpha[r]}{N_COLS - k}")
            # de-dup while preserving order
            seen = set()
            uniq = []
            for w in wells:
                if w not in seen:
                    seen.add(w)
                    uniq.append(w)
            rings.append(uniq)

        # Per-ring colour spec: (tip_color, lane, volume_uL, secondary_mix)
        # The outer-to-inner palette is red -> yellow -> green (Y+B) -> blue,
        # which reads as a rainbow on the white-paper backdrop.
        ring_specs = [
            ("red",    "red",    80, None),
            ("yellow", "yellow", 80, None),
            ("yellow", "yellow", 50, ("blue",  50)),   # green = Y + B
            ("blue",   "blue",   80, None),
        ]

        for ring_wells, (tip, lane, vol, secondary) in zip(rings, ring_specs):
            pick_single_tip(tip)
            for w_name in ring_wells:
                w = plate.wells_by_name()[w_name]
                aspirate_tracked(p300s, vol, lane)
                dispense_and_lift(p300s, vol, w)
            p300s.drop_tip()
            if secondary is not None:
                sec_lane, sec_vol = secondary
                pick_single_tip(sec_lane)
                for w_name in ring_wells:
                    w = plate.wells_by_name()[w_name]
                    aspirate_tracked(p300s, sec_vol, sec_lane)
                    p300s.dispense(sec_vol, w.bottom(2))
                    p300s.mix(2, MIX_UL, w.bottom(2))
                    p300s.move_to(w.top(z=-2))
                p300s.drop_tip()

    # =====================================================================
    # Run sequence
    # =====================================================================
    workflow_sequence = [
        plate_standard_curves,
        plate_synergy_matrix,
        plate_multiplex_blocks,
        plate_elisa_layout,
        plate_mixed_bouquet,
        plate_concentric_rings,
    ]

    protocol.home()
    protocol.set_rail_lights(True)   # booth lights on

    for i, (plate, workflow) in enumerate(zip(plates, workflow_sequence)):
        workflow(plate, i)

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

    diluent_breakdown = ", ".join(
        f"{lane}={diluent_used[lane]}" for lane in DILUENT_LANES
    )
    protocol.comment(
        "Reservoir usage (uL drawn): "
        f"red={used_ul['red']}, yellow={used_ul['yellow']}, "
        f"blue={used_ul['blue']} | diluent {diluent_breakdown}"
    )
    protocol.comment(
        "Demo complete - thanks for visiting the Future Lab Innovations booth!"
    )
