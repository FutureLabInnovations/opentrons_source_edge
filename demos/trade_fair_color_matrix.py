"""
OT-2 Trade Fair Demo  -  Color Mixing Matrix
=============================================

Autonomous, eye-catching demo for trade-fair audiences. Paints six 96-well
plates with food-dye gradients to produce a different "color matrix" on each
plate. Total runtime: ~2 hours.

Pipettes (no modules used):
  - left  : P300 Single-Channel GEN2  -> precision color accents (yellow rows)
  - right : P300 Multi-Channel  GEN2  -> fast column fills (red+blue gradients)
            and 8-tip wash step in the bulk water reservoir

Tip strategy (per user spec):
  - Single-channel rack is sectioned by color so a tip never sees more than
    one color:
        cols 1-3  -> red tips
        cols 4-6  -> yellow tips
        cols 7-9  -> blue tips
        cols 10-12-> wash/water tips
  - Multi-channel uses fresh tip columns for the first WASH_TRIGGER_PLATE
    plates, then switches to wash-and-reuse mode: tips are dipped 3x in the
    large water reservoir between colors and returned to their rack so the
    same column can be picked up again.

Materials needed
----------------
Hardware (already on robot):
  * Opentrons OT-2
  * P300 Multi-Channel GEN2  (right mount)
  * P300 Single-Channel GEN2 (left mount)

Labware:
  * 6 x corning_96_wellplate_360ul_flat   (clear, flat-bottom, slots 2,5,6,7,8,11)
  * 1 x nest_12_reservoir_15ml            (slot 4: red, yellow, blue, water, ...)
  * 1 x nest_1_reservoir_195ml            (slot 9: bulk water for wash station)
  * 3 x opentrons_96_tiprack_300ul        (slots 1,3,10)

Reagents (food-grade, non-hazardous):
  * Red, yellow, and blue food coloring (~20 mL each, diluted 1:5 in water
    in their reservoir lanes for vivid but not over-saturated color)
  * Distilled water for diluent and the wash station (~250 mL total)

Reservoir layout (NEST 12-well, slot 4):
   A1=red  A2=yellow  A3=blue  A4=diluent (water)  A5..A12=spare/waste

Setup tip:
  Place a sheet of white paper or a small LED light pad under the OT-2 deck.
  The clear flat-bottom plates light up beautifully and the gradients are
  visible from across the room.
"""

from opentrons import protocol_api

metadata = {
    "protocolName": "Trade Fair Color Matrix",
    "author": "Opentrons Demo",
    "description": "Autonomous 2-hour colorful demo using P300 multi + P300 single",
}

requirements = {"robotType": "OT-2", "apiLevel": "2.15"}


# ---------------------------------------------------------------------------
# Tunables
# ---------------------------------------------------------------------------

# Reservoir lane assignments (NEST 12-well, slot 4)
RED, YELLOW, BLUE, DILUENT = "A1", "A2", "A3", "A4"

# Single-channel tip-rack sections (1-indexed column ranges, inclusive).
# Each color only ever uses tips from its own section.
TIP_SECTIONS = {
    "red":    (1, 3),
    "yellow": (4, 6),
    "blue":   (7, 9),
    "wash":   (10, 12),
}

# After this plate index (0-based), the multi-channel switches from
# "fresh tips per color" to "wash-and-reuse" mode.
WASH_TRIGGER_PLATE = 2

# Per-plate volumes (uL). All wells receive a water base and then varying
# amounts of red, blue, and yellow to produce the color matrix.
BASE_WATER_UL    = 60          # constant water base in every well
MAX_PRIMARY_UL   = 60          # peak red/blue volume at gradient extremes
MAX_YELLOW_UL    = 50          # peak yellow accent at the bottom row
MIN_DISPENSE_UL  = 20          # P300 lower limit; volumes below this are skipped

# Pause after each plate so visitors can see the finished art.
PLATE_VIEWING_DELAY_S = 45


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------

def run(protocol: protocol_api.ProtocolContext):

    # Labware ---------------------------------------------------------------
    reservoir    = protocol.load_labware("nest_12_reservoir_15ml",   4)
    wash_station = protocol.load_labware("nest_1_reservoir_195ml",   9)

    plates = [
        protocol.load_labware(
            "corning_96_wellplate_360ul_flat", slot, f"plate {i + 1}"
        )
        for i, slot in enumerate([2, 5, 6, 7, 8, 11])
    ]

    rack_single  = protocol.load_labware("opentrons_96_tiprack_300ul", 1, "single tips")
    rack_multi_a = protocol.load_labware("opentrons_96_tiprack_300ul", 3, "multi tips A")
    rack_multi_b = protocol.load_labware("opentrons_96_tiprack_300ul", 10, "multi tips B")

    # Pipettes --------------------------------------------------------------
    p300s = protocol.load_instrument(
        "p300_single_gen2", "left", tip_racks=[rack_single]
    )
    p300m = protocol.load_instrument(
        "p300_multi_gen2",  "right", tip_racks=[rack_multi_a, rack_multi_b]
    )

    p300s.flow_rate.aspirate = 100
    p300s.flow_rate.dispense = 200
    p300m.flow_rate.aspirate = 100
    p300m.flow_rate.dispense = 200

    # Sectioned tip pools for the single-channel pipette --------------------
    # Each color reserves a contiguous column range so a tip never sees more
    # than one color.
    def section_wells(start_col, end_col):
        return [
            f"{row}{col}"
            for col in range(start_col, end_col + 1)
            for row in "ABCDEFGH"
        ]

    tip_pools = {color: section_wells(s, e) for color, (s, e) in TIP_SECTIONS.items()}
    tip_index = {color: 0 for color in tip_pools}

    def pick_single_tip(color: str) -> None:
        if tip_index[color] >= len(tip_pools[color]):
            raise RuntimeError(
                f"Out of {color} tips - section exhausted (used "
                f"{tip_index[color]}/{len(tip_pools[color])})."
            )
        well_name = tip_pools[color][tip_index[color]]
        tip_index[color] += 1
        p300s.pick_up_tip(rack_single.wells_by_name()[well_name])

    # Multi-channel tip management -----------------------------------------
    # In fresh mode (early plates) each color gets a brand-new tip column,
    # which is dropped after use. In wash mode (later plates) the same column
    # of tips is washed in the bulk water reservoir between colors and
    # returned to its rack so it can be picked up again.
    multi_columns = []
    for rack in (rack_multi_a, rack_multi_b):
        for col in range(12):
            multi_columns.append(rack.columns()[col][0])
    multi_idx = {"next": 0}  # mutable counter

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

    # ----------------------------------------------------------------------
    # Per-plate painting
    # ----------------------------------------------------------------------
    def red_volume(col: int, reverse: bool) -> int:
        # Decreasing across columns 0..11 (or reversed). Returns 0 for any
        # value below the pipette's safe minimum.
        idx = (11 - col) if not reverse else col
        v = round(MAX_PRIMARY_UL * idx / 11)
        return v if v >= MIN_DISPENSE_UL else 0

    def blue_volume(col: int, reverse: bool) -> int:
        idx = col if not reverse else (11 - col)
        v = round(MAX_PRIMARY_UL * idx / 11)
        return v if v >= MIN_DISPENSE_UL else 0

    def yellow_volume(row_idx: int) -> int:
        v = round(MAX_YELLOW_UL * row_idx / 7)
        return v if v >= MIN_DISPENSE_UL else 0

    def wells_for_pattern(pattern: str, row_idx: int):
        # Returns the column indices (0..11) that get a yellow accent for a
        # given row in this pattern.
        if pattern == "checker":
            return list(range(row_idx % 2, 12, 2))
        if pattern == "stripes":
            return list(range(0, 12, 3))
        if pattern == "diagonal":
            shift = row_idx
            return [(c + shift) % 12 for c in range(0, 12, 2)]
        # default: every column
        return list(range(12))

    def paint_plate(plate, plate_idx: int, pattern: str, reverse_primary: bool):
        wash_mode = plate_idx >= WASH_TRIGGER_PLATE
        protocol.comment(
            f"=== Plate {plate_idx + 1} | pattern={pattern} | "
            f"reverse={reverse_primary} | wash_mode={wash_mode} ==="
        )

        # 1) Multi-channel: water base in every column ---------------------
        multi_pick_fresh()
        for col in range(12):
            p300m.aspirate(BASE_WATER_UL, reservoir[DILUENT])
            p300m.dispense(BASE_WATER_UL, plate.columns()[col][0].top(-3))
        if wash_mode:
            multi_wash_in_reservoir()
            p300m.return_tip()
        else:
            p300m.drop_tip()

        # 2) Multi-channel: red gradient across columns --------------------
        multi_pick_fresh()
        for col in range(12):
            v = red_volume(col, reverse_primary)
            if v == 0:
                continue
            p300m.aspirate(v, reservoir[RED])
            p300m.dispense(v, plate.columns()[col][0].top(-3))
        if wash_mode:
            multi_wash_in_reservoir()
            p300m.return_tip()
        else:
            p300m.drop_tip()

        # 3) Multi-channel: blue gradient across columns -------------------
        multi_pick_fresh()
        for col in range(12):
            v = blue_volume(col, reverse_primary)
            if v == 0:
                continue
            p300m.aspirate(v, reservoir[BLUE])
            p300m.dispense(v, plate.columns()[col][0].top(-3))
        if wash_mode:
            multi_wash_in_reservoir()
            p300m.return_tip()
        else:
            p300m.drop_tip()

        # 4) Single-channel: yellow row accents ----------------------------
        # One fresh yellow-section tip per plate (yellow only sees yellow).
        pick_single_tip("yellow")
        for row_idx, row_letter in enumerate("ABCDEFGH"):
            v = yellow_volume(row_idx)
            if v == 0:
                continue
            for col in wells_for_pattern(pattern, row_idx):
                target = plate.wells_by_name()[f"{row_letter}{col + 1}"]
                p300s.aspirate(v, reservoir[YELLOW])
                p300s.dispense(v, target.top(-3))
        p300s.drop_tip()

        # Show off the finished plate ------------------------------------
        protocol.delay(seconds=PLATE_VIEWING_DELAY_S, msg=f"Showing plate {plate_idx + 1}")

    # ----------------------------------------------------------------------
    # Run six plates with varied patterns
    # ----------------------------------------------------------------------
    plate_specs = [
        # (pattern, reverse_primary)
        ("matrix",   False),   # plate 1: red->blue across, yellow rows top->bottom
        ("matrix",   True),    # plate 2: reversed primary direction
        ("checker",  False),   # plate 3: yellow checkerboard (wash mode kicks in)
        ("stripes",  True),    # plate 4: vertical yellow stripes, reversed primaries
        ("diagonal", False),   # plate 5: diagonal yellow march
        ("matrix",   True),    # plate 6: full-saturation finale
    ]

    protocol.home()

    for i, (pattern, reverse) in enumerate(plate_specs):
        paint_plate(plates[i], i, pattern, reverse)

    protocol.comment("Demo complete - thanks for visiting the Opentrons booth!")
