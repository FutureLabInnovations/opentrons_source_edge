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

Runtime parameters (set in the Opentrons app before starting the run):
  * Plate format -- "96-well only", "384-well only", or "Both (3 of each)"
  * Per-plate viewing delay (s) -- pause length after each finished plate;
    bump up to extend total runtime.

Materials needed
----------------
Hardware (already on robot):
  * Opentrons OT-2
  * P300 Multi-Channel GEN2  (right mount)
  * P300 Single-Channel GEN2 (left mount)

Labware (slots 2,5,6,7,8,11 hold plates; mix depends on RTP):
  * up to 6 x corning_96_wellplate_360ul_flat   (clear, flat-bottom)
  * up to 6 x corning_384_wellplate_112ul_flat  (clear, flat-bottom)
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

# 2.18+ is required for runtime parameters (add_parameters / protocol.params).
requirements = {"robotType": "OT-2", "apiLevel": "2.18"}


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

# P300 lower limit; any computed volume below this is skipped.
MIN_DISPENSE_UL = 20

# Per-plate-format configuration. The 384-well plate has half the well volume
# of the 96-well plate (112 uL vs 360 uL), denser geometry (16 rows / 24 cols),
# and an 8-channel pipette can only reach every-other row per aim, so it
# requires two aim rows ("A", "B") to address all 16 rows.
PLATE_CONFIGS = {
    "96": {
        "load_name":      "corning_96_wellplate_360ul_flat",
        "n_rows":         8,
        "n_cols":         12,
        "base_water_ul":  60,
        "max_primary_ul": 60,
        "max_yellow_ul":  50,
        "multi_aim_rows": ["A"],
    },
    "384": {
        "load_name":      "corning_384_wellplate_112ul_flat",
        "n_rows":         16,
        "n_cols":         24,
        # Tighter volumes to fit the 112 uL well: 20 + 45 + 40 = 105 uL max.
        "base_water_ul":  20,
        "max_primary_ul": 45,
        "max_yellow_ul":  40,
        "multi_aim_rows": ["A", "B"],
    },
}

# Six plate slots; this maps the plate_format RTP to a list of plate kinds
# (one per slot, in the order slots [2, 5, 6, 7, 8, 11] are filled).
FORMAT_TO_KINDS = {
    "96":   ["96"]  * 6,
    "384":  ["384"] * 6,
    "both": ["96", "96", "96", "384", "384", "384"],
}


# ---------------------------------------------------------------------------
# 3x5 pixel font for 384-well text rendering ("FUTURE LAB INNOVATIONS")
# ---------------------------------------------------------------------------
# Each glyph is 5 rows tall and 3 columns wide. Letters are spaced one column
# apart, so each character occupies 4 columns total (3 + gap). With 24 plate
# columns we fit up to six 3-wide glyphs per line; with 16 plate rows we fit
# two lines stacked vertically.
FONT_3x5 = {
    "F": ["###", "#..", "##.", "#..", "#.."],
    "U": ["#.#", "#.#", "#.#", "#.#", "###"],
    "T": ["###", ".#.", ".#.", ".#.", ".#."],
    "R": ["##.", "#.#", "##.", "#.#", "#.#"],
    "E": ["###", "#..", "##.", "#..", "###"],
    "L": ["#..", "#..", "#..", "#..", "###"],
    "A": [".#.", "#.#", "###", "#.#", "#.#"],
    "B": ["##.", "#.#", "##.", "#.#", "##."],
    "I": ["###", ".#.", ".#.", ".#.", "###"],
    "N": ["#.#", "##.", "###", ".##", "#.#"],
    "O": ["###", "#.#", "#.#", "#.#", "###"],
    "V": ["#.#", "#.#", "#.#", "#.#", ".#."],
    "S": ["###", "#..", "###", "..#", "###"],
    " ": ["...", "...", "...", "...", "..."],
}

# Two-line layout per 384-well plate. Together these spell
# "FUTURE LAB INNOVATIONS" across two consecutive 384 plates.
TEXT_LINES_384 = [
    ("FUTURE", "LAB"),
    ("INNOVA", "TIONS"),
]

# Volume of the dye dispensed into each "lit" pixel on a 384 text plate.
# 60 uL is well above MIN_DISPENSE_UL and gives a visibly-saturated letter
# on top of the 20 uL water base (total 80 uL, well below the 112 uL well
# capacity).
TEXT_PIXEL_UL = 60


# ---------------------------------------------------------------------------
# Runtime parameters
# ---------------------------------------------------------------------------

def add_parameters(parameters):
    parameters.add_str(
        variable_name="plate_format",
        display_name="Plate format",
        description=(
            "Which plate format to demo. 'Both' loads three of each "
            "side-by-side on the deck."
        ),
        default="96",
        choices=[
            {"display_name": "96-well only (6 plates)",  "value": "96"},
            {"display_name": "384-well only (6 plates)", "value": "384"},
            {"display_name": "Both (3 x 96 + 3 x 384)",  "value": "both"},
        ],
    )
    parameters.add_int(
        variable_name="viewing_delay_s",
        display_name="Per-plate viewing delay (s)",
        description=(
            "Pause after each finished plate so visitors can admire the "
            "result. Increase to extend total runtime."
        ),
        default=90,
        minimum=0,
        maximum=600,
        unit="s",
    )


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------

def run(protocol: protocol_api.ProtocolContext):

    plate_format    = protocol.params.plate_format
    viewing_delay_s = protocol.params.viewing_delay_s
    plate_kinds     = FORMAT_TO_KINDS[plate_format]

    # Labware ---------------------------------------------------------------
    reservoir    = protocol.load_labware("nest_12_reservoir_15ml",   4)
    wash_station = protocol.load_labware("nest_1_reservoir_195ml",   9)

    # Load each plate slot according to its kind from the RTP.
    plates = []
    for i, slot in enumerate([2, 5, 6, 7, 8, 11]):
        kind_name = plate_kinds[i]
        cfg = PLATE_CONFIGS[kind_name]
        plate = protocol.load_labware(
            cfg["load_name"], slot, f"plate {i + 1} ({kind_name}-well)"
        )
        plates.append((plate, cfg, kind_name))

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
    # Per-plate painting (works for both 96- and 384-well plates)
    # ----------------------------------------------------------------------
    def primary_volume(col: int, n_cols: int, max_ul: int, decreasing: bool) -> int:
        # Linear ramp across the plate's columns. `decreasing=True` peaks at
        # col 0; otherwise peaks at the last column. Volumes below the
        # pipette's safe minimum are returned as 0 (skipped).
        denom = max(1, n_cols - 1)
        idx = (denom - col) if decreasing else col
        v = round(max_ul * idx / denom)
        return v if v >= MIN_DISPENSE_UL else 0

    def yellow_volume(row_idx: int, n_rows: int, max_ul: int) -> int:
        denom = max(1, n_rows - 1)
        v = round(max_ul * row_idx / denom)
        return v if v >= MIN_DISPENSE_UL else 0

    def wells_for_pattern(pattern: str, row_idx: int, n_cols: int):
        # Returns the column indices (0..n_cols-1) that get a yellow accent
        # for a given row in this pattern.
        if pattern == "checker":
            return list(range(row_idx % 2, n_cols, 2))
        if pattern == "stripes":
            return list(range(0, n_cols, 3))
        if pattern == "diagonal":
            return [(c + row_idx) % n_cols for c in range(0, n_cols, 2)]
        return list(range(n_cols))  # default: every column

    def paint_matrix_plate(plate, cfg, kind_name: str, plate_idx: int,
                           pattern: str, reverse_primary: bool):
        wash_mode = plate_idx >= WASH_TRIGGER_PLATE
        n_rows = cfg["n_rows"]
        n_cols = cfg["n_cols"]
        aim_rows = cfg["multi_aim_rows"]
        base_ul    = cfg["base_water_ul"]
        primary_ul = cfg["max_primary_ul"]
        yellow_ul  = cfg["max_yellow_ul"]

        protocol.comment(
            f"=== Plate {plate_idx + 1} ({kind_name}-well matrix) | pattern={pattern} | "
            f"reverse={reverse_primary} | wash_mode={wash_mode} ==="
        )

        # Helper: dispense `vol` of `source` into every (aim_row, col) pair.
        # For 96-well aim_rows=["A"]; for 384-well aim_rows=["A","B"] so each
        # column gets two passes (covering all 16 rows via 8-channel offsets).
        def multi_paint(source, vol_for_col):
            for col in range(n_cols):
                v = vol_for_col(col)
                if v == 0:
                    continue
                for aim in aim_rows:
                    target = plate.wells_by_name()[f"{aim}{col + 1}"]
                    p300m.aspirate(v, source)
                    p300m.dispense(v, target.top(-3))

        def finish_multi():
            if wash_mode:
                multi_wash_in_reservoir()
                p300m.return_tip()
            else:
                p300m.drop_tip()

        # 1) Multi-channel: water base in every column ---------------------
        multi_pick_fresh()
        multi_paint(reservoir[DILUENT], lambda c: base_ul)
        finish_multi()

        # 2) Multi-channel: red gradient across columns --------------------
        multi_pick_fresh()
        multi_paint(
            reservoir[RED],
            lambda c: primary_volume(c, n_cols, primary_ul, decreasing=not reverse_primary),
        )
        finish_multi()

        # 3) Multi-channel: blue gradient across columns -------------------
        multi_pick_fresh()
        multi_paint(
            reservoir[BLUE],
            lambda c: primary_volume(c, n_cols, primary_ul, decreasing=reverse_primary),
        )
        finish_multi()

        # 4) Single-channel: yellow row accents ----------------------------
        # One fresh yellow-section tip per plate.
        pick_single_tip("yellow")
        rows = "ABCDEFGHIJKLMNOP"[:n_rows]
        for row_idx, row_letter in enumerate(rows):
            v = yellow_volume(row_idx, n_rows, yellow_ul)
            if v == 0:
                continue
            for col in wells_for_pattern(pattern, row_idx, n_cols):
                target = plate.wells_by_name()[f"{row_letter}{col + 1}"]
                p300s.aspirate(v, reservoir[YELLOW])
                p300s.dispense(v, target.top(-3))
        p300s.drop_tip()

        # (Viewing delay handled by the outer dispatcher.)

    # ----------------------------------------------------------------------
    # Per-plate text rendering for 384-well plates
    # ----------------------------------------------------------------------
    def paint_text_plate(plate, cfg, plate_idx: int,
                         top_word: str, bottom_word: str):
        wash_mode = plate_idx >= WASH_TRIGGER_PLATE
        n_rows  = cfg["n_rows"]      # 16
        n_cols  = cfg["n_cols"]      # 24
        aim_rows = cfg["multi_aim_rows"]
        base_ul = cfg["base_water_ul"]

        protocol.comment(
            f"=== Plate {plate_idx + 1} (384-well text: '{top_word}' / "
            f"'{bottom_word}') | wash_mode={wash_mode} ==="
        )

        # 1) Multi-channel: water base across all 24 columns x 2 aim rows.
        multi_pick_fresh()
        for col in range(n_cols):
            for aim in aim_rows:
                target = plate.wells_by_name()[f"{aim}{col + 1}"]
                p300m.aspirate(base_ul, reservoir[DILUENT])
                p300m.dispense(base_ul, target.top(-3))
        if wash_mode:
            multi_wash_in_reservoir()
            p300m.return_tip()
        else:
            p300m.drop_tip()

        # 2) Single-channel: paint each text line in BLUE dye.
        # Top line at rows 2-6, bottom line at rows 9-13. Both vertically
        # well-centered within the 16-row plate (~2 rows margin top/bottom,
        # 2 rows gap between lines).
        rows_alphabet = "ABCDEFGHIJKLMNOP"

        def render_line(text: str, row_offset: int):
            text = text.upper()
            glyph_width = 3
            gap = 1
            stride = glyph_width + gap
            text_width = len(text) * stride - gap if text else 0
            col_offset = max(0, (n_cols - text_width) // 2)
            for char_idx, ch in enumerate(text):
                glyph = FONT_3x5.get(ch, FONT_3x5[" "])
                base_col = col_offset + char_idx * stride
                for r in range(5):
                    for c in range(glyph_width):
                        if glyph[r][c] != "#":
                            continue
                        plate_row = row_offset + r
                        plate_col = base_col + c
                        if not (0 <= plate_row < n_rows and 0 <= plate_col < n_cols):
                            continue
                        target = plate.wells_by_name()[
                            f"{rows_alphabet[plate_row]}{plate_col + 1}"
                        ]
                        p300s.aspirate(TEXT_PIXEL_UL, reservoir[BLUE])
                        p300s.dispense(TEXT_PIXEL_UL, target.top(-3))

        # Use the BLUE-section single-channel tips (one tip for the full plate;
        # both lines share it since blue only ever sees blue).
        pick_single_tip("blue")
        render_line(top_word,    row_offset=2)
        render_line(bottom_word, row_offset=9)
        p300s.drop_tip()

    # ----------------------------------------------------------------------
    # Run sequence: dispatch each plate to its kind-specific painter
    # ----------------------------------------------------------------------
    matrix_specs = [
        # (pattern, reverse_primary) -- cycled across 96-well plates only
        ("matrix",   False),
        ("matrix",   True),
        ("checker",  False),
        ("stripes",  True),
        ("diagonal", False),
        ("matrix",   True),
    ]

    protocol.home()

    idx_96 = 0
    idx_384 = 0
    for i, (plate, cfg, kind_name) in enumerate(plates):
        if kind_name == "384":
            top_word, bottom_word = TEXT_LINES_384[idx_384 % len(TEXT_LINES_384)]
            paint_text_plate(plate, cfg, i, top_word, bottom_word)
            idx_384 += 1
        else:
            pattern, reverse = matrix_specs[idx_96 % len(matrix_specs)]
            paint_matrix_plate(plate, cfg, kind_name, i, pattern, reverse)
            idx_96 += 1

        protocol.delay(
            seconds=viewing_delay_s,
            msg=f"Showing plate {i + 1} ({kind_name}-well)",
        )

    protocol.comment("Demo complete - thanks for visiting the Opentrons booth!")
